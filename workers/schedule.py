"""
Crawler schedule definitions for cron/systemd.

Run manually (`run_scheduled.py`), via `run_daemon.py` / docker `crawler`, or API background refresh.
Search returns pre-indexed Postgres rows immediately; crawls update the index in the background.

Recommended intervals:
  github   every 30–60 minutes
  hn       every 15–30 minutes
  arxiv    every 6–12 hours
  rss      every 30–60 minutes (when implemented)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Awaitable

# Type alias for async runner functions imported at runtime.
Runner = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class CrawlJob:
    name: str
    source_type: str
    interval_hint: str
    module: str
    description: str
    # How often run_daemon.py runs this job (minutes).
    daemon_interval_minutes: int = 60


CRAWL_JOBS: dict[str, CrawlJob] = {
    "github": CrawlJob(
        name="github",
        source_type="github",
        interval_hint="30-60m",
        module="ingest.run_github",
        description="GitHub repo search for vibe-coder projects",
        daemon_interval_minutes=20,
    ),
    "hn": CrawlJob(
        name="hn",
        source_type="hackernews",
        interval_hint="~5m",
        module="ingest.run_hn",
        description="Hacker News Algolia stories",
        daemon_interval_minutes=5,
    ),
    "arxiv": CrawlJob(
        name="arxiv",
        source_type="arxiv",
        interval_hint="~3h",
        module="ingest.run_arxiv",
        description="arXiv papers for builders",
        daemon_interval_minutes=180,
    ),
    "rss": CrawlJob(
        name="rss",
        source_type="rss",
        interval_hint="30-60m",
        module="ingest.run_rss",
        description="RSS/blog feeds (stub)",
        daemon_interval_minutes=60,
    ),
    "embeddings": CrawlJob(
        name="embeddings",
        source_type="maintenance",
        interval_hint="after crawls",
        module="ingest.backfill_embeddings",
        description="Backfill NULL embeddings for hybrid search",
        daemon_interval_minutes=15,
    ),
}
