#!/usr/bin/env python3
"""
Run a scheduled crawl job by name.

Usage:
  python run_scheduled.py github
  python run_scheduled.py hn
  python run_scheduled.py arxiv
  python run_scheduled.py embeddings
  python run_scheduled.py --list

Wire to cron (examples in crontab.example).
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import sys
from pathlib import Path

WORKERS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKERS_ROOT))

from schedule import CRAWL_JOBS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("run_scheduled")


def _run_github() -> None:
    from ingest.run_github import main as github_main

    github_main()


async def _run_hn() -> None:
    from ingest.run_hn import main as hn_main

    await hn_main()


async def _run_arxiv() -> None:
    from ingest.run_arxiv import main as arxiv_main

    await arxiv_main()


async def _run_embeddings() -> None:
    from ingest.backfill_embeddings import main as emb_main

    await emb_main()


async def _run_rss() -> None:
    from ingest.run_rss import main as rss_main

    if asyncio.iscoroutinefunction(rss_main):
        await rss_main()
    else:
        rss_main()


ASYNC_RUNNERS = {
    "hn": _run_hn,
    "arxiv": _run_arxiv,
    "rss": _run_rss,
    "embeddings": _run_embeddings,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Build Radar crawl job")
    parser.add_argument("job", nargs="?", choices=list(CRAWL_JOBS.keys()))
    parser.add_argument("--list", action="store_true", help="List available jobs")
    args = parser.parse_args()

    if args.list or not args.job:
        print("Available crawl jobs:\n")
        for name, job in CRAWL_JOBS.items():
            print(f"  {name:12} every {job.interval_hint:8}  {job.description}")
        if not args.job:
            sys.exit(0)
        return

    job = CRAWL_JOBS[args.job]
    logger.info("Starting job=%s (%s)", job.name, job.interval_hint)

    if job.name == "github":
        _run_github()
    else:
        asyncio.run(ASYNC_RUNNERS[job.name]())

    logger.info("Finished job=%s", job.name)


if __name__ == "__main__":
    main()
