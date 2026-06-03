"""
Optional background index refresh — never blocks search.

Triggers worker jobs when the index is stale and no crawl is already running.
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import db
from ..config import get_settings

logger = logging.getLogger(__name__)

_spawn_lock = asyncio.Lock()
_last_trigger_at: datetime | None = None

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKERS_ROOT = REPO_ROOT / "workers"


def _workers_python() -> str:
    return os.getenv("WORKERS_PYTHON", sys.executable)


async def crawl_in_progress() -> bool:
    row = await db.fetchrow(
        """
        SELECT COUNT(*)::int AS c
        FROM crawl_runs
        WHERE status = 'running'
          AND started_at > now() - interval '3 hours'
        """
    )
    return bool(row and row["c"] > 0)


async def minutes_since_last_finish(source_type: str) -> float | None:
    row = await db.fetchrow(
        """
        SELECT EXTRACT(EPOCH FROM (now() - MAX(finished_at))) / 60.0 AS minutes
        FROM crawl_runs
        WHERE status = 'done' AND source_type = $1
        """,
        source_type,
    )
    if not row or row["minutes"] is None:
        return None
    return float(row["minutes"])


def _spawn(job: str, extra_args: list[str] | None = None) -> None:
    if not WORKERS_ROOT.is_dir():
        logger.warning("Workers dir not found at %s — skip background crawl", WORKERS_ROOT)
        return
    cmd = [_workers_python(), "run_scheduled.py", job, *(extra_args or [])]
    logger.info("Background crawl spawn: %s", " ".join(cmd))
    subprocess.Popen(
        cmd,
        cwd=WORKERS_ROOT,
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


async def maybe_refresh_index() -> None:
    """Fire-and-forget staleness check; safe to call after every search."""
    settings = get_settings()
    if not settings.background_crawl_enabled:
        return

    global _last_trigger_at
    now = datetime.now(timezone.utc)
    cooldown = timedelta(minutes=settings.background_crawl_cooldown_minutes)
    if _last_trigger_at and now - _last_trigger_at < cooldown:
        return

    async with _spawn_lock:
        if _last_trigger_at and now - _last_trigger_at < cooldown:
            return
        if await crawl_in_progress():
            return

        count_row = await db.fetchrow("SELECT COUNT(*)::int AS c FROM artifacts")
        artifact_count = int(count_row["c"]) if count_row else 0

        # Always prefer a fast HN pass on search (Algolia — does not block search path).
        _spawn("hn")
        _last_trigger_at = now

        gh_age = await minutes_since_last_finish("github")
        if gh_age is None or gh_age >= settings.background_crawl_github_stale_minutes:
            _spawn("github")


async def maybe_bootstrap_on_startup() -> None:
    settings = get_settings()
    if not settings.bootstrap_crawl_on_start:
        return
    if await crawl_in_progress():
        return
    count_row = await db.fetchrow("SELECT COUNT(*)::int AS c FROM artifacts")
    if count_row and int(count_row["c"]) >= settings.bootstrap_min_artifacts:
        return
    if not WORKERS_ROOT.is_dir():
        return
    logger.info("Sparse index — starting bootstrap_index.py in background")
    subprocess.Popen(
        [_workers_python(), "bootstrap_index.py"],
        cwd=WORKERS_ROOT,
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
