from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

from ..config import get_settings
from ..schemas import SearchResponse, SearchResultOut
from ..services.background_crawl import maybe_refresh_index
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
    results = [SearchResultOut(**r) for r in result["results"]]
    return SearchResponse(
        query=result["query"],
        intent=result["intent"],
        results=results,
        total=result["total"],
    )
