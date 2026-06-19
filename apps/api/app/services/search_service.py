"""Hybrid search: FTS (ts_rank_cd) + pgvector cosine + RRF + metadata ranking.

IMPORTANT: This path never calls crawlers or external APIs.
All artifact text, embeddings, and scores are precomputed at ingest time.
Search only reads Postgres and embeds the user query locally (for vector leg).
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Optional

from .. import db
from ..config import get_settings
from ..models import record_to_artifact
from ..utils.text import to_pgvector
from .embedding_service import embed_text
from .extraction_service import extract_project_intent
from .intent_retrieval import (
    build_fts_or_query,
    build_fts_plaintext,
    build_retrieval_context,
    enrich_intent,
)
from .ranking_service import (
    build_why_relevant,
    compute_final_score,
    project_relevance_score,
    reciprocal_rank_fusion,
)

CANDIDATE_LIMIT = 60


def normalize_query(q: str) -> str:
    q = q.strip()
    q = re.sub(r"\s+", " ", q)
    return q


def _build_filter_clauses(
    filters: dict[str, Any],
    *,
    param_offset: int,
) -> tuple[str, list[Any], int]:
    """SQL AND clauses for optional filters."""
    clauses: list[str] = []
    args: list[Any] = []
    idx = param_offset

    mapping = {
        "tag": "tags",
        "tool": "tools",
        "framework": "frameworks",
        "language": "languages",
    }
    for key, col in mapping.items():
        val = filters.get(key)
        if val:
            clauses.append(f" AND ${idx} = ANY({col})")
            args.append(val)
            idx += 1

    for key in ("source_type", "artifact_type"):
        val = filters.get(key)
        if val:
            clauses.append(f" AND {key} = ${idx}")
            args.append(val)
            idx += 1

    if filters.get("min_quality_score") is not None:
        clauses.append(f" AND quality_score >= ${idx}")
        args.append(float(filters["min_quality_score"]))
        idx += 1

    if filters.get("max_hype_risk") is not None:
        clauses.append(f" AND hype_risk_score <= ${idx}")
        args.append(float(filters["max_hype_risk"]))
        idx += 1

    return "".join(clauses), args, idx


def _merge_hits(*hit_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by id; keep best kw_rank / lowest vec_distance."""
    by_id: dict[str, dict[str, Any]] = {}
    for hits in hit_lists:
        for item in hits:
            aid = str(item["id"])
            prev = by_id.get(aid)
            if prev is None:
                by_id[aid] = item
                continue
            if (item.get("kw_rank") or 0) > (prev.get("kw_rank") or 0):
                prev["kw_rank"] = item["kw_rank"]
            if item.get("vec_distance") is not None:
                if prev.get("vec_distance") is None or item["vec_distance"] < prev["vec_distance"]:
                    prev["vec_distance"] = item["vec_distance"]
    return list(by_id.values())


async def _fts_query(
    tsquery_sql: str,
    tsquery_arg: str,
    limit: int,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run FTS with ts_rank_cd (normalization 32)."""
    if not tsquery_arg or not tsquery_arg.strip():
        return []
    filter_sql, filter_args, _ = _build_filter_clauses(filters, param_offset=2)
    sql = f"""
        SELECT
            a.*,
            ts_rank_cd(a.search_vector, {tsquery_sql}, 32) AS kw_rank
        FROM artifacts a
        WHERE a.search_vector @@ {tsquery_sql}
        {filter_sql}
        ORDER BY kw_rank DESC
        LIMIT {limit}
    """
    try:
        rows = await db.fetch(sql, tsquery_arg, *filter_args)
    except Exception:  # noqa: BLE001 — invalid tsquery syntax
        return []
    return [record_to_artifact(r) for r in rows]


async def keyword_search(
    query: str,
    intent: dict[str, Any],
    limit: int,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Multi-strategy FTS: OR intent terms, plain intent text, websearch on query."""
    or_q = build_fts_or_query(intent)
    plain = build_fts_plaintext(intent, query)

    hits_or = await _fts_query("to_tsquery('english', $1)", or_q, limit, filters) if or_q else []
    hits_plain = await _fts_query("plainto_tsquery('english', $1)", plain, limit, filters) if plain else []
    hits_web = await _fts_query("websearch_to_tsquery('english', $1)", query, limit, filters)

    merged = _merge_hits(hits_or, hits_plain, hits_web)
    merged.sort(key=lambda x: float(x.get("kw_rank") or 0), reverse=True)
    return merged[:limit]


async def vector_search(
    embedding: list[float],
    limit: int,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """pgvector cosine distance (<=>); lower is more similar."""
    vec_literal = to_pgvector(embedding)
    if not vec_literal:
        return []

    filter_sql, filter_args, _ = _build_filter_clauses(filters, param_offset=2)
    sql = f"""
        SELECT
            a.*,
            (a.embedding <=> $1::vector) AS vec_distance,
            (1.0 - (a.embedding <=> $1::vector)) AS vec_similarity
        FROM artifacts a
        WHERE a.embedding IS NOT NULL
        {filter_sql}
        ORDER BY vec_distance ASC
        LIMIT {limit}
    """
    settings = get_settings()
    min_sim = settings.search_min_vector_similarity
    rows = await db.fetch(sql, vec_literal, *filter_args)
    results = []
    for r in rows:
        art = record_to_artifact(r)
        dist = float(r["vec_distance"]) if r.get("vec_distance") is not None else 1.0
        sim = max(0.0, 1.0 - dist)
        if sim < min_sim:
            continue
        art["vec_distance"] = dist
        art["vec_similarity"] = sim
        results.append(art)
    return results


async def intent_term_search(
    intent: dict[str, Any],
    limit: int,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Boost artifacts whose tags/tools/frameworks align with extracted intent."""
    terms = dedupe_terms(intent)
    if not terms:
        return []

    n = len(terms)
    filter_sql, filter_args, _ = _build_filter_clauses(filters, param_offset=n + 1)
    conditions = []
    for i in range(1, n + 1):
        conditions.append(
            f"(EXISTS (SELECT 1 FROM unnest(tags) t WHERE lower(t) = lower(${i})) "
            f"OR EXISTS (SELECT 1 FROM unnest(tools) t WHERE lower(t) = lower(${i})) "
            f"OR EXISTS (SELECT 1 FROM unnest(frameworks) t WHERE lower(t) = lower(${i})) "
            f"OR title ILIKE '%' || ${i} || '%' OR summary ILIKE '%' || ${i} || '%')"
        )
    where = " OR ".join(conditions)
    sql = f"""
        SELECT *, 0.55::float AS kw_rank
        FROM artifacts
        WHERE ({where})
        {filter_sql}
        ORDER BY quality_score DESC
        LIMIT {limit}
    """
    rows = await db.fetch(sql, *terms, *filter_args)
    return [record_to_artifact(r) for r in rows]


def dedupe_terms(intent: dict[str, Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in (intent.get("tags") or []) + (intent.get("tools") or []) + (intent.get("search_terms") or []):
        t = raw.lower().strip()
        if t and t not in seen and len(t) >= 3:
            seen.add(t)
            out.append(t)
    return out[:12]


async def hybrid_search(
    query: str,
    *,
    limit: int = 20,
    filters: Optional[dict[str, Any]] = None,
    rerank: Optional[bool] = None,
) -> dict[str, Any]:
    """Full hybrid pipeline with project-context awareness + stage-2 rerank."""
    filters = {k: v for k, v in (filters or {}).items() if v is not None}
    q = normalize_query(query)
    intent = enrich_intent(q, extract_project_intent(q))
    retrieval_text = build_retrieval_context(q, intent)

    # Embed query only (artifacts already have precomputed vectors in DB).
    embedding = embed_text(retrieval_text)

    if embedding:
        keyword_hits, intent_hits, vector_hits = await asyncio.gather(
            keyword_search(q, intent, CANDIDATE_LIMIT, filters),
            intent_term_search(intent, 40, filters),
            vector_search(embedding, CANDIDATE_LIMIT, filters),
        )
    else:
        keyword_hits, intent_hits = await asyncio.gather(
            keyword_search(q, intent, CANDIDATE_LIMIT, filters),
            intent_term_search(intent, 40, filters),
        )
        vector_hits = []

    if not keyword_hits and not vector_hits:
        keyword_hits = await _fallback_ilike_search(q, intent, 50, filters)

    rrf_scores = reciprocal_rank_fusion(
        keyword_hits,
        vector_hits,
        intent_hits,
        weights=[1.0, 0.9, 0.45],
    )

    by_id: dict[str, dict[str, Any]] = {}
    for item in keyword_hits + vector_hits + intent_hits:
        aid = str(item["id"])
        if aid not in by_id:
            by_id[aid] = dict(item)
        else:
            cur = by_id[aid]
            if (item.get("kw_rank") or 0) > (cur.get("kw_rank") or 0):
                cur["kw_rank"] = item["kw_rank"]
            if item.get("vec_similarity") is not None:
                cur["vec_similarity"] = item.get("vec_similarity")
            if item.get("vec_distance") is not None:
                cur["vec_distance"] = item.get("vec_distance")

    ranked: list[dict[str, Any]] = []
    for aid, artifact in by_id.items():
        rrf = rrf_scores.get(aid, 0.0)
        kw = float(artifact.get("kw_rank") or 0)
        vec_sim = artifact.get("vec_similarity")
        rel = project_relevance_score(
            artifact,
            intent,
            kw_rank=kw if kw else None,
            vec_similarity=float(vec_sim) if vec_sim is not None else None,
        )
        artifact["project_relevance_score"] = rel
        artifact["final_score"] = compute_final_score(artifact, intent, rrf, project_relevance=rel)
        artifact["why_relevant"] = build_why_relevant(artifact, intent)
        ranked.append(artifact)

    settings = get_settings()
    min_rel = settings.search_min_project_relevance
    min_final = settings.search_min_final_score

    filtered = [
        a
        for a in ranked
        if a["final_score"] >= min_final
        and (
            a["project_relevance_score"] >= min_rel
            or float(a.get("kw_rank") or 0) >= 0.08
            or float(a.get("vec_similarity") or 0) >= settings.search_min_vector_similarity
        )
    ]
    # If thresholds are too strict for a small index, keep best-scoring candidates.
    if len(filtered) < min(3, limit) and ranked:
        filtered = ranked[: max(limit, 3)]

    filtered.sort(key=lambda x: x["final_score"], reverse=True)

    # Stage 2: cross-encoder reranking of the top candidates (retrieve-then-rerank).
    use_rerank = settings.rerank_enabled if rerank is None else rerank
    if use_rerank and filtered:
        from .reranking_service import rerank as cross_rerank

        n = min(settings.rerank_candidates, len(filtered))
        if cross_rerank(q, filtered, n):
            w = settings.rerank_weight
            for a in filtered[:n]:
                rs = a.get("rerank_score")
                if rs is not None:
                    a["final_score"] = w * float(rs) + (1.0 - w) * a["final_score"]
            filtered.sort(key=lambda x: x["final_score"], reverse=True)

    results = filtered[:limit]

    return {
        "query": q,
        "intent": intent,
        "results": results,
        "total": len(filtered),
    }


async def _fallback_ilike_search(
    query: str,
    intent: dict[str, Any],
    limit: int,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Last-resort term match when FTS/embeddings return nothing."""
    terms = dedupe_terms(intent)
    if not terms:
        terms = [t for t in re.findall(r"[a-zA-Z0-9]+", query.lower()) if len(t) > 2][:8]
    if not terms:
        return []

    or_block = " OR ".join(
        [
            f"(title ILIKE ${i} OR summary ILIKE ${i} OR what_it_helps_build ILIKE ${i} "
            f"OR array_to_string(tags, ' ') ILIKE ${i})"
            for i in range(1, len(terms) + 1)
        ]
    )
    term_params = [f"%{t}%" for t in terms]
    filter_sql, filter_args, _ = _build_filter_clauses(
        filters, param_offset=len(term_params) + 1
    )
    sql = f"""
        SELECT *, 0.25::float AS kw_rank
        FROM artifacts
        WHERE ({or_block})
        {filter_sql}
        ORDER BY quality_score DESC
        LIMIT {limit}
    """
    rows = await db.fetch(sql, *term_params, *filter_args)
    return [record_to_artifact(r) for r in rows]
