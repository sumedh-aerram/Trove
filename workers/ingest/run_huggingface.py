#!/usr/bin/env python3
"""Hugging Face Hub crawler — indexes ready-to-use models.

Uses only the public Hub list API (JSON). No model weights are downloaded, so
this is light and fast regardless of network throttling.
"""
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
from common.huggingface import hf_model_to_artifact  # noqa: E402
from common.relevance import embed_query, passes  # noqa: E402
from common.topics import HF_QUERIES  # noqa: E402

HF_API = "https://huggingface.co/api/models"


async def crawl_query(pool, client: httpx.AsyncClient, query: str) -> tuple[int, int, int]:
    found = inserted = updated = 0
    resp = await client.get(
        HF_API,
        params={
            "search": query,
            "sort": "downloads",
            "direction": "-1",
            "limit": 25,
            "full": "true",
        },
    )
    resp.raise_for_status()
    models = resp.json()
    query_embedding = embed_query(query)
    async with pool.acquire() as conn:
        for model in models:
            found += 1
            artifact = hf_model_to_artifact(model)
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
    queries = rotate("hf", HF_QUERIES, window_size("HF_WINDOW", 6))
    total_ins = total_upd = 0
    headers = {"User-Agent": "Trove/0.1"}
    async with httpx.AsyncClient(timeout=60.0, headers=headers) as client:
        for query in queries:
            print(f"HF: {query}")
            try:
                found, inserted, updated = await crawl_query(pool, client, query)
            except Exception as exc:  # noqa: BLE001
                print(f"  error: {exc}")
                continue
            total_ins += inserted
            total_upd += updated
            print(f"  found={found} new={inserted} refreshed={updated}")
            await asyncio.sleep(0.5)
    print(f"HF run complete: +{total_ins} NEW, {total_upd} refreshed across {len(queries)} queries")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
