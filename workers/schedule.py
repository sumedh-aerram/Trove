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
    # Rebalanced mix: GitHub/arXiv are higher-substance (real code, papers) than
    # most Hacker News link posts, so GitHub leads and HN is slowed down. This
    # shifts the corpus away from being ~85% HN and lifts result relevance.
    "github": CrawlJob(
        name="github",
        source_type="github",
        interval_hint="10-15m",
        module="ingest.run_github",
        description="GitHub repo search for buildable projects",
        daemon_interval_minutes=10,
    ),
    "hn": CrawlJob(
        name="hn",
        source_type="hackernews",
        interval_hint="~20m",
        module="ingest.run_hn",
        description="Hacker News Algolia stories",
        daemon_interval_minutes=20,
    ),
    "arxiv": CrawlJob(
        name="arxiv",
        source_type="arxiv",
        interval_hint="~2h",
        module="ingest.run_arxiv",
        description="arXiv papers for builders",
        daemon_interval_minutes=120,
    ),
    "hf": CrawlJob(
        name="hf",
        source_type="huggingface",
        interval_hint="~90m",
        module="ingest.run_huggingface",
        description="Hugging Face models (high-substance, ready to use)",
        daemon_interval_minutes=90,
    ),
    "rss": CrawlJob(
        name="rss",
        source_type="rss",
        interval_hint="30-60m",
        module="ingest.run_rss",
        description="RSS feeds from builder/AI-eng blogs",
        daemon_interval_minutes=45,
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
