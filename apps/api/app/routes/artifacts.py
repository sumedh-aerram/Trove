from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import db
from ..models import record_to_artifact
from ..schemas import ArtifactListResponse, ArtifactOut

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


def _filter_sql_and_args(
    tag: Optional[str],
    tool: Optional[str],
    framework: Optional[str],
    language: Optional[str],
    source_type: Optional[str],
    artifact_type: Optional[str],
    min_quality_score: Optional[float],
    max_hype_risk: Optional[float],
) -> tuple[str, list]:
    conditions = ["WHERE 1=1"]
    args: list = []
    idx = 1

    def add(sql: str, val) -> None:
        nonlocal idx
        conditions.append(f" AND {sql.format(n=idx)}")
        args.append(val)
        idx += 1

    if tag:
        add("${n} = ANY(tags)", tag)
    if tool:
        add("${n} = ANY(tools)", tool)
    if framework:
        add("${n} = ANY(frameworks)", framework)
    if language:
        add("${n} = ANY(languages)", language)
    if source_type:
        add("source_type = ${n}", source_type)
    if artifact_type:
        add("artifact_type = ${n}", artifact_type)
    if min_quality_score is not None:
        add("quality_score >= ${n}", min_quality_score)
    if max_hype_risk is not None:
        add("hype_risk_score <= ${n}", max_hype_risk)

    return " ".join(conditions), args


@router.get("", response_model=ArtifactListResponse)
async def list_artifacts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tag: Optional[str] = None,
    tool: Optional[str] = None,
    framework: Optional[str] = None,
    language: Optional[str] = None,
    source_type: Optional[str] = None,
    artifact_type: Optional[str] = None,
    min_quality_score: Optional[float] = None,
    max_hype_risk: Optional[float] = None,
) -> ArtifactListResponse:
    where, args = _filter_sql_and_args(
        tag, tool, framework, language, source_type, artifact_type,
        min_quality_score, max_hype_risk,
    )
    n = len(args) + 1
    list_args = [*args, limit, offset]

    count_row = await db.fetchrow(f"SELECT COUNT(*)::int AS total FROM artifacts {where}", *args)
    total = int(count_row["total"]) if count_row else 0

    rows = await db.fetch(
        f"""
        SELECT * FROM artifacts
        {where}
        ORDER BY quality_score DESC, created_at DESC
        LIMIT ${n} OFFSET ${n + 1}
        """,
        *list_args,
    )
    items = [ArtifactOut(**record_to_artifact(r)) for r in rows]
    return ArtifactListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{artifact_id}", response_model=ArtifactOut)
async def get_artifact(artifact_id: str) -> ArtifactOut:
    row = await db.fetchrow("SELECT * FROM artifacts WHERE id = $1::uuid", artifact_id)
    if not row:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return ArtifactOut(**record_to_artifact(row))
