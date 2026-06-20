#!/usr/bin/env python3
"""RSS/Atom crawler — indexes builder + AI-engineering blog posts."""
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

from common.cursor import rotate, window_size  # noqa: E402
from common.db import get_pool, upsert_artifact  # noqa: E402
from common.relevance import embed_query, passes  # noqa: E402
from common.rss import rss_entry_to_artifact  # noqa: E402
from common.topics import RSS_FEEDS  # noqa: E402

_ATOM = "{http://www.w3.org/2005/Atom}"


def _text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def parse_feed(xml_text: str) -> list[dict]:
    """Handle both RSS 2.0 (<item>) and Atom (<entry>)."""
    entries: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return entries

    # RSS 2.0
    for item in root.iter("item"):
        link = _text(item.find("link"))
        entries.append({
            "title": _text(item.find("title")),
            "link": link,
            "summary": _text(item.find("description")),
            "published": _text(item.find("pubDate")) or None,
        })
    # Atom
    for entry in root.iter(f"{_ATOM}entry"):
        link_el = entry.find(f"{_ATOM}link")
        link = link_el.get("href") if link_el is not None else ""
        summary = _text(entry.find(f"{_ATOM}summary")) or _text(entry.find(f"{_ATOM}content"))
        entries.append({
            "title": _text(entry.find(f"{_ATOM}title")),
            "link": link,
            "summary": summary,
            "published": _text(entry.find(f"{_ATOM}updated")) or _text(entry.find(f"{_ATOM}published")) or None,
        })
    return entries


async def crawl_feed(pool, client: httpx.AsyncClient, name: str, url: str) -> tuple[int, int, int]:
    found = inserted = updated = 0
    resp = await client.get(url, follow_redirects=True)
    resp.raise_for_status()
    entries = parse_feed(resp.text)[:25]
    # Feed topic embedding gates off-topic posts (e.g. personal life updates).
    query_embedding = embed_query(f"{name} software AI engineering build tutorial")
    async with pool.acquire() as conn:
        for entry in entries:
            if not entry.get("link") or not entry.get("title"):
                continue
            found += 1
            artifact = rss_entry_to_artifact(entry, name)
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
    feeds = rotate("rss", RSS_FEEDS, window_size("RSS_WINDOW", 4))
    total_ins = total_upd = 0
    headers = {"User-Agent": "Trove/0.1 (+https://github.com/sumedh-aerram/Trove)"}
    async with httpx.AsyncClient(timeout=45.0, headers=headers) as client:
        for name, url in feeds:
            print(f"RSS: {name}")
            try:
                found, inserted, updated = await crawl_feed(pool, client, name, url)
            except Exception as exc:  # noqa: BLE001
                print(f"  error: {exc}")
                continue
            total_ins += inserted
            total_upd += updated
            print(f"  found={found} new={inserted} refreshed={updated}")
            await asyncio.sleep(0.5)
    print(f"RSS run complete: +{total_ins} NEW, {total_upd} refreshed across {len(feeds)} feeds")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
