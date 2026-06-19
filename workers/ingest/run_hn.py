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

from common.cursor import rotate, window_size  # noqa: E402
from common.db import get_pool, upsert_artifact  # noqa: E402
from common.hn import hn_hit_to_artifact  # noqa: E402
from common.relevance import embed_query, passes  # noqa: E402
from common.topics import HN_TERMS  # noqa: E402

HN_SEARCH = "https://hn.algolia.com/api/v1/search"
HN_SEARCH_BY_DATE = "https://hn.algolia.com/api/v1/search_by_date"


async def crawl_term(pool, term: str) -> tuple[int, int, int]:
    found = inserted = skipped = 0
    query_embedding = embed_query(term)
    # Pull both the top stories (by relevance) AND the newest stories (by date).
    # The "by date" feed rotates over time, which is what actually adds NEW builds.
    async with httpx.AsyncClient(timeout=30.0) as client:
        hits: list[dict] = []
        seen: set = set()
        for endpoint, pages in ((HN_SEARCH, 2), (HN_SEARCH_BY_DATE, 1)):
            for page in range(pages):
                resp = await client.get(
                    endpoint,
                    params={"query": term, "tags": "story", "hitsPerPage": 40, "page": page},
                )
                resp.raise_for_status()
                page_hits = resp.json().get("hits", [])
                for h in page_hits:
                    oid = h.get("objectID")
                    if oid in seen:
                        continue
                    seen.add(oid)
                    hits.append(h)
                if len(page_hits) < 40:
                    break

    updated = 0
    async with pool.acquire() as conn:
        for hit in hits:
            # Skip near-zero-signal chatter; keep anything with a little traction.
            if int(hit.get("points") or 0) < 3:
                continue
            found += 1
            artifact = hn_hit_to_artifact(hit)
            ok, _ = passes(artifact, query_embedding)
            if not ok:
                skipped += 1
                continue
            res = await upsert_artifact(conn, artifact)
            if res == "inserted":
                inserted += 1
            elif res == "updated":
                updated += 1
    if skipped:
        print(f"  (skipped {skipped} off-topic/low-signal)")
    return found, inserted, updated


async def main() -> None:
    pool = await get_pool()
    # Rotate through the full term list across runs so the index keeps growing.
    terms = rotate("hn", HN_TERMS, window_size("HN_WINDOW", 10))
    total_ins = total_upd = 0
    for term in terms:
        print(f"HN search: {term}")
        found, inserted, updated = await crawl_term(pool, term)
        total_ins += inserted
        total_upd += updated
        print(f"  found={found} new={inserted} refreshed={updated}")
    print(f"HN run complete: +{total_ins} NEW, {total_upd} refreshed across {len(terms)} terms")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
