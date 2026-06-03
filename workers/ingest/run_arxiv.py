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
from common.db import get_pool, upsert_artifact  # noqa: E402

ARXIV_API = "http://export.arxiv.org/api/query"

TOPICS = [
    "code generation software engineering",
    "repository-level code generation",
    "automated program repair",
    "retrieval augmented generation RAG",
    "multimodal agents",
    "AI coding assistants",
    "efficient inference LLM",
]


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


async def crawl_topic(pool, topic: str) -> tuple[int, int]:
    found = inserted = 0
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            ARXIV_API,
            params={"search_query": f"all:{topic}", "start": 0, "max_results": 15},
        )
        resp.raise_for_status()
        entries = _parse_feed(resp.text)

    async with pool.acquire() as conn:
        for entry in entries:
            found += 1
            artifact = arxiv_entry_to_artifact(entry)
            if await upsert_artifact(conn, artifact):
                inserted += 1
    return found, inserted


async def main() -> None:
    pool = await get_pool()
    for topic in TOPICS:
        print(f"arXiv: {topic}")
        found, inserted = await crawl_topic(pool, topic)
        print(f"  found={found} inserted={inserted}")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
