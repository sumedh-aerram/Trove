"""GitHub API helpers (shared patterns with workers/common/github_client.py)."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
MAX_RETRIES = 4


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    for attempt in range(1, MAX_RETRIES + 1):
        resp = await client.request(method, url, headers=headers, params=params)
        if resp.status_code in (403, 429) and "rate limit" in resp.text.lower():
            reset = resp.headers.get("X-RateLimit-Reset")
            wait = 60
            if reset:
                wait = max(int(reset) - int(time.time()) + 1, 1)
            wait = min(wait, 300)
            logger.warning("GitHub rate limit — sleeping %ss", wait)
            await asyncio.sleep(wait)
            continue
        if resp.status_code >= 500 and attempt < MAX_RETRIES:
            await asyncio.sleep(min(2**attempt, 20))
            continue
        return resp
    return resp


async def search_repositories(
    query: str,
    *,
    per_page: int = 30,
    page: int = 1,
    token: Optional[str] = None,
) -> list[dict[str, Any]]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = token or os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await _request_with_retry(
            client,
            "GET",
            f"{GITHUB_API}/search/repositories",
            headers=headers,
            params={"q": query, "per_page": per_page, "page": page, "sort": "updated"},
        )
        if resp.status_code == 422:
            logger.error("Invalid GitHub search: %s", query)
            return []
        resp.raise_for_status()
        return resp.json().get("items", [])


async def fetch_readme(full_name: str, token: Optional[str] = None) -> str:
    headers = {"Accept": "application/vnd.github.raw", "X-GitHub-Api-Version": "2022-11-28"}
    token = token or os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    owner, repo = full_name.split("/", 1)
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await _request_with_retry(
            client,
            "GET",
            f"{GITHUB_API}/repos/{owner}/{repo}/readme",
            headers=headers,
        )
        if resp.status_code == 404:
            return ""
        if resp.status_code != 200:
            return ""
        return resp.text
