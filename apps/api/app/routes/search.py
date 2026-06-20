from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query
from pydantic import BaseModel

from ..config import get_settings
from ..schemas import SearchResponse, SearchResultOut
from ..services import feedback_service
from ..services.background_crawl import maybe_refresh_index
from ..services.landscape_service import build_landscape
from ..services.search_service import hybrid_search

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    background_tasks: BackgroundTasks,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    tag: Optional[str] = None,
    tool: Optional[str] = None,
    framework: Optional[str] = None,
    language: Optional[str] = None,
    artifact_type: Optional[str] = None,
    source_type: Optional[str] = None,
    min_quality_score: Optional[float] = None,
    max_hype_risk: Optional[float] = None,
) -> SearchResponse:
    filters = {
        "tag": tag,
        "tool": tool,
        "framework": framework,
        "language": language,
        "artifact_type": artifact_type,
        "source_type": source_type,
        "min_quality_score": min_quality_score,
        "max_hype_risk": max_hype_risk,
    }
    result = await hybrid_search(q, limit=limit, filters=filters)
    settings = get_settings()
    if settings.background_crawl_on_search:
        background_tasks.add_task(maybe_refresh_index)

    # Log the impression for the self-improving loop (best-effort, off the hot path).
    background_tasks.add_task(
        feedback_service.log_search, result["query"], result["results"], result["intent"]
    )

    landscape = build_landscape(result["query"], result["intent"], result["results"])
    results = [SearchResultOut(**r) for r in result["results"]]
    return SearchResponse(
        query=result["query"],
        intent=result["intent"],
        results=results,
        total=result["total"],
        clusters=landscape["clusters"],
        landscape_summary=landscape["summary"],
        query_confidence=landscape["query_confidence"],
        query_advice=landscape["query_advice"],
        suggested_query=landscape["suggested_query"],
    )


class ClickEvent(BaseModel):
    query: str
    artifact_id: str
    position: Optional[int] = None


@router.post("/events/click")
async def log_click(event: ClickEvent) -> dict:
    """Record that a user opened a result for a query (implicit relevance signal)."""
    await feedback_service.log_click(event.query, event.artifact_id, event.position)
    return {"ok": True}
