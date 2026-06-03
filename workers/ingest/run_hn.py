#!/usr/bin/env python3
"""Hacker News Algolia crawler."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

WORKERS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKERS_ROOT))

from dotenv import load_dotenv

load_dotenv(WORKERS_ROOT.parent / ".env")

from common.db import get_pool, upsert_artifact  # noqa: E402
from common.hn import hn_hit_to_artifact  # noqa: E402

HN_SEARCH = "https://hn.algolia.com/api/v1/search"

TERMS = [
    "AI hackathon project",
    "Next.js AI app",
    "RAG app",
    "LangChain",
    "LlamaIndex",
    "MCP server",
    "Claude Code",
    "Cursor",
    "AI agent",
    "open source AI app",
    "computer vision app",
    "Whisper app",
    "Chrome extension AI",
]


async def crawl_term(pool, term: str) -> tuple[int, int]:
    found = inserted = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(HN_SEARCH, params={"query": term, "tags": "story", "hitsPerPage": 25})
        resp.raise_for_status()
        hits = resp.json().get("hits", [])

    async with pool.acquire() as conn:
        for hit in hits:
            found += 1
            artifact = hn_hit_to_artifact(hit)
            if await upsert_artifact(conn, artifact):
                inserted += 1
    return found, inserted


async def main() -> None:
    pool = await get_pool()
    for term in TERMS:
        print(f"HN search: {term}")
        found, inserted = await crawl_term(pool, term)
        print(f"  found={found} inserted={inserted}")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
