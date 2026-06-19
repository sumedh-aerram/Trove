#!/usr/bin/env python3
"""
Background crawl daemon — keeps the shared Postgres index fresh.

Used by docker-compose `crawler` service. Search/MCP never wait on this;
they only read pre-indexed rows.

On start: optional bootstrap when artifact count is low, then periodic jobs.
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

WORKERS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKERS_ROOT))

from dotenv import load_dotenv

load_dotenv(WORKERS_ROOT.parent / ".env")

from schedule import CRAWL_JOBS  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("crawl_daemon")

# Jobs the daemon rotates through (rss omitted until implemented).
DAEMON_JOBS = ("hn", "github", "arxiv", "embeddings")


def _run_job(job_name: str) -> None:
    logger.info("=== daemon job: %s ===", job_name)
    result = subprocess.run(
        [sys.executable, "run_scheduled.py", job_name],
        cwd=WORKERS_ROOT,
    )
    if result.returncode != 0:
        logger.warning("Job %s exited with code %s", job_name, result.returncode)


def _maybe_bootstrap() -> None:
    if os.getenv("SKIP_BOOTSTRAP", "").lower() in ("1", "true", "yes"):
        return
    subprocess.run(
        [sys.executable, "bootstrap_index.py"],
        cwd=WORKERS_ROOT,
        check=False,
    )


def main() -> None:
    logger.info("Trove crawl daemon starting (DATABASE_URL set=%s)", bool(os.getenv("DATABASE_URL")))
    _maybe_bootstrap()

    last_run: dict[str, float] = {name: 0.0 for name in DAEMON_JOBS}
    tick_seconds = int(os.getenv("CRAWL_DAEMON_TICK_SECONDS", "30"))

    while True:
        now = time.time()
        for job_name in DAEMON_JOBS:
            job = CRAWL_JOBS[job_name]
            interval = job.daemon_interval_minutes * 60
            if now - last_run[job_name] >= interval:
                _run_job(job_name)
                last_run[job_name] = time.time()
        time.sleep(tick_seconds)


if __name__ == "__main__":
    main()
