"""Usage logging for the self-improving search loop.

Every search records an "impression" (which artifact ids were shown, and at what
rank). Clicks and stars record which result the user chose, tied to the query
that produced it. This is the raw signal the offline harvester turns into (a)
new eval queries and (b) position-bias-corrected (query, relevant-doc) training
pairs.

All writes are best-effort and never block or fail a search response.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .. import db

logger = logging.getLogger(__name__)

# Cap stored impression depth: positions past this carry little learning signal.
IMPRESSION_DEPTH = 20


async def log_search(query: str, results: list[dict[str, Any]], intent: dict[str, Any]) -> None:
    impression = [
        {"id": str(r["id"]), "pos": i}
        for i, r in enumerate(results[:IMPRESSION_DEPTH])
    ]
    try:
        await db.execute(
            """
            INSERT INTO search_events (event_type, query, project_context, impression)
            VALUES ('search', $1, $2::jsonb, $3::jsonb)
            """,
            query,
            {"project_type": intent.get("project_type")},
            impression,
        )
    except Exception as exc:  # noqa: BLE001 — logging must never break search
        logger.debug("log_search failed: %s", exc)


async def log_click(query: str, artifact_id: str, position: Optional[int]) -> None:
    try:
        await db.execute(
            """
            INSERT INTO search_events (event_type, query, clicked_artifact_id, position)
            VALUES ('click', $1, $2::uuid, $3)
            """,
            query,
            artifact_id,
            position,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("log_click failed: %s", exc)


async def log_star(query: Optional[str], artifact_id: str, position: Optional[int]) -> None:
    if not query:
        return
    try:
        await db.execute(
            """
            INSERT INTO search_events (event_type, query, saved_artifact_id, position)
            VALUES ('star', $1, $2::uuid, $3)
            """,
            query,
            artifact_id,
            position,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("log_star failed: %s", exc)
