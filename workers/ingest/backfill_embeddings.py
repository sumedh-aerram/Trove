#!/usr/bin/env python3
"""Backfill NULL embeddings for all artifacts using SentenceTransformers."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

WORKERS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKERS_ROOT))
sys.path.insert(0, str(WORKERS_ROOT.parent / "apps" / "api"))

from dotenv import load_dotenv

load_dotenv(WORKERS_ROOT.parent / ".env")

from app.services.embedding_service import embed_text, warmup  # noqa: E402
from app.services.extraction_service import build_embedding_text  # noqa: E402
from app.utils.text import to_pgvector  # noqa: E402
from common.db import get_pool  # noqa: E402


async def main() -> None:
    warmup()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, summary, what_it_helps_build, technical_core, "
            "practical_use_case, how_to_remix, implementation_steps, setup_commands, "
            "tags, tools, frameworks, languages, apis, models "
            "FROM artifacts WHERE embedding IS NULL"
        )
        print(f"Backfilling {len(rows)} artifacts...")
        for row in rows:
            text = build_embedding_text(dict(row))
            vec = embed_text(text)
            if not vec:
                print(f"  skip {row['id']} (no embedding)")
                continue
            await conn.execute(
                "UPDATE artifacts SET embedding = $2::vector WHERE id = $1::uuid",
                str(row["id"]),
                to_pgvector(vec),
            )
            print(f"  updated {row['title'][:60]}")
    await pool.close()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
