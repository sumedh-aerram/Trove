#!/usr/bin/env python3
"""arXiv API crawler for research papers relevant to builders."""
from __future__ import annotations

import asyncio
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

WORKERS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKERS_ROOT))

from dotenv import load_dotenv

load_dotenv(WORKERS_ROOT.parent / ".env")

from common.arxiv import arxiv_entry_to_artifact  # noqa: E402
from common.cursor import rotate, window_size  # noqa: E402
from common.db import get_pool, upsert_artifact  # noqa: E402
from common.relevance import embed_query, passes  # noqa: E402
from common.topics import ARXIV_CATEGORIES, ARXIV_TOPICS  # noqa: E402

# Dedicated harvesting host (arXiv asks programmatic access to use export.*).
ARXIV_API = "https://export.arxiv.org/api/query"


def _parse_feed(xml_text: str) -> list[dict]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    entries = []
    for entry in root.findall("atom:entry", ns):
        entries.append(
            {
                "id": entry.findtext("atom:id", default="", namespaces=ns),
                "title": entry.findtext("atom:title", default="", namespaces=ns),
                "summary": entry.findtext("atom:summary", default="", namespaces=ns),
            }
        )
    return entries


def _build_query(topic: str, categories: list[str]) -> str:
    cat = " OR ".join(f"cat:{c}" for c in categories)
    return f"all:{topic} AND ({cat})"


async def crawl_topic(pool, client: httpx.AsyncClient, topic: str) -> tuple[int, int]:
    found = inserted = 0
    # Newest first for freshness; bias to builder-relevant CS categories.
    resp = await client.get(
        ARXIV_API,
        params={
            "search_query": _build_query(topic, ARXIV_CATEGORIES),
            "start": 0,
            "max_results": 25,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        },
    )
    resp.raise_for_status()
    entries = _parse_feed(resp.text)

    updated = 0
    query_embedding = embed_query(topic)
    async with pool.acquire() as conn:
        for entry in entries:
            found += 1
            artifact = arxiv_entry_to_artifact(entry)
            ok, _ = passes(artifact, query_embedding)
            if not ok:
                continue
            res = await upsert_artifact(conn, artifact)
            if res == "inserted":
                inserted += 1
            elif res == "updated":
                updated += 1
    return found, inserted, updated


async def main() -> None:
    pool = await get_pool()
    topics = rotate("arxiv", ARXIV_TOPICS, window_size("ARXIV_WINDOW", 5))
    total_ins = total_upd = 0
    async with httpx.AsyncClient(timeout=60.0, headers={"User-Agent": "BuildRadar/0.1"}) as client:
        for topic in topics:
            print(f"arXiv: {topic}")
            found, inserted, updated = await crawl_topic(pool, client, topic)
            total_ins += inserted
            total_upd += updated
            print(f"  found={found} new={inserted} refreshed={updated}")
            # arXiv asks for a ~1s pause between programmatic requests.
            await asyncio.sleep(1.2)
    print(f"arXiv run complete: +{total_ins} NEW, {total_upd} refreshed across {len(topics)} topics")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
