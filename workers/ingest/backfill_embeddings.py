#!/usr/bin/env python3
"""Backfill NULL embeddings for all artifacts using SentenceTransformers."""
from __future__ import annotations

import argparse
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

_ARTIFACT_COLS = (
    "id, title, artifact_type, summary, what_it_helps_build, technical_core, "
    "practical_use_case, how_to_remix, implementation_steps, setup_commands, "
    "tags, tools, frameworks, languages, apis, models"
)


async def main(*, reembed_all: bool) -> None:
    warmup()
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = "" if reembed_all else "WHERE embedding IS NULL"
        rows = await conn.fetch(f"SELECT {_ARTIFACT_COLS} FROM artifacts {where}")
        label = "Re-embedding" if reembed_all else "Backfilling"
        print(f"{label} {len(rows)} artifacts...")
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
            title = str(row["title"] or "")[:60]
            print(f"  updated {title}")
    await pool.close()
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill artifact embeddings")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Re-embed every artifact (use after changing build_embedding_text)",
    )
    args = parser.parse_args()
    asyncio.run(main(reembed_all=args.all))
