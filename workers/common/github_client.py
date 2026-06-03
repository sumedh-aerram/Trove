"""Async GitHub REST client with rate-limit handling and retries."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
DEFAULT_PER_PAGE = 30
MAX_RETRIES = 5


class GitHubRateLimitError(Exception):
    """Raised when rate limit persists after waits."""


class GitHubClient:
    def __init__(self, token: str | None = None, *, timeout: float = 45.0) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN") or None
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout

    def _headers(self, *, accept: str = "application/vnd.github+json") -> dict[str, str]:
        headers = {
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def __aenter__(self) -> GitHubClient:
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API,
            timeout=self._timeout,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Use GitHubClient as async context manager")
        return self._client

    def _log_rate_limit(self, resp: httpx.Response) -> None:
        remaining = resp.headers.get("X-RateLimit-Remaining")
        limit = resp.headers.get("X-RateLimit-Limit")
        reset = resp.headers.get("X-RateLimit-Reset")
        if remaining is not None:
            logger.info(
                "GitHub rate limit: %s/%s remaining, reset=%s",
                remaining,
                limit,
                reset,
            )

    async def _sleep_for_rate_limit(self, resp: httpx.Response) -> None:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            wait = max(int(retry_after), 1)
        else:
            reset = resp.headers.get("X-RateLimit-Reset")
            if reset:
                wait = max(int(reset) - int(time.time()) + 1, 1)
            else:
                wait = 60
        wait = min(wait, 300)
        logger.warning("Rate limited by GitHub — sleeping %ss", wait)
        await asyncio.sleep(wait)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        accept: str = "application/vnd.github+json",
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await self.client.request(
                    method,
                    path,
                    params=params,
                    headers=self._headers(accept=accept),
                )
                self._log_rate_limit(resp)

                if resp.status_code in (403, 429):
                    body = resp.text.lower()
                    if "rate limit" in body or resp.status_code == 429:
                        if attempt >= MAX_RETRIES:
                            raise GitHubRateLimitError(resp.text[:200])
                        await self._sleep_for_rate_limit(resp)
                        continue

                if resp.status_code >= 500:
                    if attempt >= MAX_RETRIES:
                        resp.raise_for_status()
                    wait = min(2**attempt, 30)
                    logger.warning("GitHub %s — retry in %ss", resp.status_code, wait)
                    await asyncio.sleep(wait)
                    continue

                return resp
            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt >= MAX_RETRIES:
                    raise
                wait = min(2**attempt, 20)
                logger.warning("GitHub timeout — retry in %ss", wait)
                await asyncio.sleep(wait)
        if last_exc:
            raise last_exc
        raise RuntimeError("GitHub request failed")

    async def search_repositories(
        self,
        query: str,
        *,
        per_page: int = DEFAULT_PER_PAGE,
        page: int = 1,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return (items, total_count)."""
        resp = await self.request(
            "GET",
            "/search/repositories",
            params={
                "q": query,
                "per_page": per_page,
                "page": page,
                "sort": "updated",
                "order": "desc",
            },
        )
        if resp.status_code == 422:
            logger.error("Invalid GitHub search query: %s — %s", query, resp.text[:200])
            return [], 0
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", []), int(data.get("total_count", 0))

    async def fetch_readme(self, full_name: str) -> str:
        """Return README body or empty string if missing."""
        owner, repo = full_name.split("/", 1)
        resp = await self.request(
            "GET",
            f"/repos/{owner}/{repo}/readme",
            accept="application/vnd.github.raw",
        )
        if resp.status_code == 404:
            logger.debug("No README for %s", full_name)
            return ""
        if resp.status_code != 200:
            logger.warning("README fetch %s: HTTP %s", full_name, resp.status_code)
            return ""
        return resp.text

    async def fetch_repo(self, full_name: str) -> dict[str, Any] | None:
        """Fetch full repository metadata."""
        owner, repo = full_name.split("/", 1)
        resp = await self.request("GET", f"/repos/{owner}/{repo}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
