"""Index freshness and health stats for the frontend."""
from __future__ import annotations

from fastapi import APIRouter

from .. import db
from ..config import get_settings
from ..services.background_crawl import crawl_in_progress

router = APIRouter(tags=["stats"])


@router.get("/stats")
async def get_stats() -> dict:
    settings = get_settings()
    row = await db.fetchrow(
        """
        SELECT
          COUNT(*)::int AS artifact_count,
          COUNT(embedding)::int AS embeddings_count,
          MAX(last_crawled_at) AS last_crawl_at,
          MAX(updated_at) AS last_updated_at
        FROM artifacts
        """
    )
    crawl_rows = await db.fetch(
        """
        SELECT source_type, MAX(finished_at) AS last_finished
        FROM crawl_runs
        WHERE status = 'done'
        GROUP BY source_type
        """
    )
    in_progress = await crawl_in_progress()
    count = int(row["artifact_count"]) if row else 0

    return {
        "artifact_count": count,
        "embeddings_count": int(row["embeddings_count"]) if row else 0,
        "last_crawl_at": row["last_crawl_at"].isoformat() if row and row["last_crawl_at"] else None,
        "last_updated_at": row["last_updated_at"].isoformat() if row and row["last_updated_at"] else None,
        "crawl_by_source": {
            r["source_type"]: r["last_finished"].isoformat() if r["last_finished"] else None
            for r in crawl_rows
        },
        "search_mode": "preindexed",
        "crawl_in_progress": in_progress,
        "background_crawl_enabled": settings.background_crawl_enabled,
        "index_is_sparse": count < settings.bootstrap_min_artifacts,
        "note": (
            "Search returns instantly from Postgres. "
            "Background crawls refresh the index; search again to see new artifacts."
        ),
    }
