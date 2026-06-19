#!/usr/bin/env python3
"""
One-shot index bootstrap when the DB has few artifacts (e.g. fresh clone).

Runs fast sources first, then a capped GitHub crawl, then embedding backfill.
Safe to run while the API is up — upserts by canonical_url.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

WORKERS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKERS_ROOT))

from dotenv import load_dotenv

load_dotenv(WORKERS_ROOT.parent / ".env")

from common.db import get_pool  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bootstrap_index")


async def artifact_count() -> int:
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            return int(await conn.fetchval("SELECT COUNT(*)::int FROM artifacts") or 0)
    finally:
        await pool.close()


def _run(cmd: list[str]) -> None:
    logger.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, cwd=WORKERS_ROOT, check=False)


async def main_async(min_artifacts: int, github_query_limit: int) -> None:
    count = await artifact_count()
    if count >= min_artifacts:
        logger.info("Index has %s artifacts (>= %s) — skip bootstrap", count, min_artifacts)
        return

    logger.info("Index has %s artifacts — bootstrapping…", count)

    _run([sys.executable, "ingest/run_hn.py"])

    gh_cmd = [sys.executable, "ingest/run_github.py"]
    if github_query_limit > 0:
        gh_cmd.extend(["--limit-queries", str(github_query_limit)])
    _run(gh_cmd)

    _run([sys.executable, "ingest/backfill_embeddings.py"])

    final = await artifact_count()
    logger.info("Bootstrap finished — %s artifacts in index", final)


def main() -> None:
    p = argparse.ArgumentParser(description="Bootstrap Trove index")
    p.add_argument(
        "--min-artifacts",
        type=int,
        default=int(os.getenv("BOOTSTRAP_MIN_ARTIFACTS", "40")),
        help="Skip if index already has this many rows",
    )
    p.add_argument(
        "--github-query-limit",
        type=int,
        default=int(os.getenv("BOOTSTRAP_GITHUB_QUERY_LIMIT", "7")),
        help="Cap starter GitHub queries during bootstrap (0 = all)",
    )
    args = p.parse_args()
    asyncio.run(main_async(args.min_artifacts, args.github_query_limit))


if __name__ == "__main__":
    main()
