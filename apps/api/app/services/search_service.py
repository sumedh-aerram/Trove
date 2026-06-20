"""Hybrid search: FTS (ts_rank_cd) + pgvector cosine + RRF + metadata ranking.

IMPORTANT: This path never calls crawlers or external APIs.
All artifact text, embeddings, and scores are precomputed at ingest time.
Search only reads Postgres and embeds the user query locally (for vector leg).
"""
from __future__ import annotations

import asyncio
import math
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

# Wider first-stage net: retrieval recall (not ranking) is the bottleneck, so
# we pull more candidates per leg before fusion. Scoring them is cheap.
CANDIDATE_LIMIT = 100


def _dedupe_key(artifact: dict[str, Any]) -> str:
    """Collapse the same underlying thing arriving from multiple sources.

    A repo found on GitHub and linked from a Hacker News post should appear once.
    Falls back to a normalized title so near-identical entries don't both show.
    """
    url = (artifact.get("source_url") or artifact.get("canonical_url") or "").lower()
    m = re.search(r"github\.com/([^/]+/[^/#?]+)", url)
    if m:
        return "gh:" + m.group(1).rstrip("/").removesuffix(".git")
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9.]+)", url)
    if m:
        return "arxiv:" + m.group(1)
    title = re.sub(r"[^a-z0-9]+", "", (artifact.get("title") or "").lower())
    return "t:" + title if title else "id:" + str(artifact.get("id"))


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the highest scoring item per dedupe key, preserving order."""
    best: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for item in items:
        key = _dedupe_key(item)
        if key in best:
            kept = out[best[key]]
            if float(item.get("final_score") or 0) > float(kept.get("final_score") or 0):
                out[best[key]] = item
            continue
        best[key] = len(out)
        out.append(item)
    return out


def _token_set(a: dict[str, Any]) -> set[str]:
    """Topic fingerprint for diversity: tags/tools/frameworks + title words."""
    toks = set()
    for key in ("tags", "tools", "frameworks", "languages"):
        for x in (a.get(key) or []):
            toks.add(str(x).lower())
    for w in re.findall(r"[a-z0-9]+", (a.get("title") or "").lower()):
        if len(w) >= 4:
            toks.add(w)
    return toks


def _mmr(items: list[dict[str, Any]], lambda_: float, limit: int) -> list[dict[str, Any]]:
    """Maximal Marginal Relevance reranking using Jaccard topic similarity.

    Greedily selects results that are relevant (high final_score) yet dissimilar
    to what was already picked, so the top of the list is not five flavors of the
    same repo. Relevance order is the input order (already scored/sorted).
    """
    if lambda_ >= 1.0 or len(items) <= 1:
        return items[:limit]
    n = min(limit, len(items))
    pool = items[: max(limit * 2, n)]
    sets = [_token_set(a) for a in pool]
    # normalized relevance (input rank -> 1..0) keeps the two terms comparable.
    rel = {id(a): (len(pool) - i) / len(pool) for i, a in enumerate(pool)}

    selected: list[dict[str, Any]] = []
    selected_idx: list[int] = []
    remaining = list(range(len(pool)))
    while remaining and len(selected) < n:
        best_i, best_score = remaining[0], -1e9
        for i in remaining:
            if selected_idx:
                sim = max(
                    (len(sets[i] & sets[j]) / len(sets[i] | sets[j]) if (sets[i] | sets[j]) else 0.0)
                    for j in selected_idx
                )
            else:
                sim = 0.0
            score = lambda_ * rel[id(pool[i])] - (1.0 - lambda_) * sim
            if score > best_score:
                best_score, best_i = score, i
        selected.append(pool[best_i])
        selected_idx.append(best_i)
        remaining.remove(best_i)
    return selected


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
    min_similarity: Optional[float] = None,
) -> list[dict[str, Any]]:
    """pgvector cosine distance (<=>); lower is more similar.

    `min_similarity=None` uses the configured gate; pass 0.0 to get the raw,
    un-gated candidate pool (used by the eval/tuning harness).
    """
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
    min_sim = settings.search_min_vector_similarity if min_similarity is None else min_similarity
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


async def _noop_hits() -> list[dict[str, Any]]:
    """Awaitable empty list, so the gather call stays uniform when no embedding."""
    return []


def _parse_vec(raw: Any) -> Optional[list[float]]:
    """pgvector returns its value as a '[...]' string; parse to a float list."""
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        return [float(x) for x in raw]
    try:
        import json as _json

        return [float(x) for x in _json.loads(raw)]
    except Exception:  # noqa: BLE001
        return None


async def prf_vector_hits(
    base_embedding: list[float],
    initial_hits: list[dict[str, Any]],
    limit: int,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Vector-side Rocchio pseudo-relevance feedback.

    Treats the top-k first-pass vector hits as "pseudo relevant", averages their
    precomputed embeddings into a centroid, nudges the query embedding toward it,
    and re-probes. Expands recall semantically without touching the lexical query.
    """
    settings = get_settings()
    top = initial_hits[: settings.prf_top_k]
    if not top:
        return []
    ids = [h["id"] for h in top]
    rows = await db.fetch(
        "SELECT embedding FROM artifacts WHERE id = ANY($1::uuid[]) AND embedding IS NOT NULL",
        ids,
    )
    vecs = [v for v in (_parse_vec(r["embedding"]) for r in rows) if v]
    if not vecs:
        return []

    dim = len(base_embedding)
    centroid = [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]
    beta = settings.prf_beta
    expanded = [base_embedding[i] + beta * centroid[i] for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in expanded)) or 1.0
    expanded = [x / norm for x in expanded]

    return await vector_search(expanded, limit, filters, min_similarity=0.0)


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


async def retrieve_legs(
    query: str,
    *,
    candidate_limit: int = CANDIDATE_LIMIT,
    filters: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return the raw, un-gated retrieval legs for offline scoring / tuning.

    Mirrors the candidate-gathering half of hybrid_search but does NOT gate,
    fuse, or rank. The eval/tuning harness re-implements scoring on top of this
    so different fusion weights / thresholds can be measured without re-querying.
    """
    filters = {k: v for k, v in (filters or {}).items() if v is not None}
    q = normalize_query(query)
    intent = enrich_intent(q, extract_project_intent(q))
    retrieval_text = build_retrieval_context(q, intent)

    embedding = embed_text(retrieval_text)
    keyword_hits, intent_hits, vector_hits = await asyncio.gather(
        keyword_search(q, intent, candidate_limit, filters),
        intent_term_search(intent, max(40, candidate_limit), filters),
        vector_search(embedding, candidate_limit, filters, min_similarity=0.0) if embedding else _noop_hits(),
    )

    if not keyword_hits and not vector_hits:
        keyword_hits = await _fallback_ilike_search(q, intent, 50, filters)

    return {
        "query": q,
        "intent": intent,
        "keyword_hits": keyword_hits,
        "vector_hits": vector_hits,
        "intent_hits": intent_hits,
    }


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

    # Vector leg participates in fusion broadly (low floor); the configured
    # similarity threshold is applied only as a filter escape below. This
    # matches how scripts/tune_search.py modeled the fusion.
    embedding = embed_text(retrieval_text)
    keyword_hits, intent_hits, vector_hits = await asyncio.gather(
        keyword_search(q, intent, CANDIDATE_LIMIT, filters),
        intent_term_search(intent, 40, filters),
        vector_search(embedding, CANDIDATE_LIMIT, filters, min_similarity=0.0) if embedding else _noop_hits(),
    )

    # Optional second vector probe via pseudo-relevance feedback (eval-gated).
    if embedding and get_settings().prf_enabled and vector_hits:
        prf_hits = await prf_vector_hits(embedding, vector_hits, CANDIDATE_LIMIT, filters)
        if prf_hits:
            vector_hits = _merge_hits(vector_hits, prf_hits)

    if not keyword_hits and not vector_hits:
        keyword_hits = await _fallback_ilike_search(q, intent, 50, filters)

    # Fusion weights tuned via scripts/tune_search.py (keyword leg up, vector
    # leg down: the field-weighted FTS outperforms the weak 384d embeddings).
    rrf_scores = reciprocal_rank_fusion(
        keyword_hits,
        vector_hits,
        intent_hits,
        weights=[1.31, 0.60, 0.28],
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

    # Collapse the same repo/paper arriving from multiple sources.
    filtered = _dedupe(filtered)
    filtered.sort(key=lambda x: x["final_score"], reverse=True)

    # Stage 2a: learned reranker (LambdaMART). Reorders the gated candidates by a
    # model trained on relevance, replacing the hand-tuned linear order. The
    # linear blend still does the gating above; LTR refines the ordering.
    if settings.ltr_enabled and filtered:
        from . import ltr_service

        if ltr_service.rerank(filtered, rrf_scores, intent):
            ss = [a["ltr_score"] for a in filtered]
            lo, hi = min(ss), max(ss)
            rng = (hi - lo) or 1.0
            for a in filtered:
                a["final_score"] = (a["ltr_score"] - lo) / rng
            filtered.sort(key=lambda x: x["final_score"], reverse=True)

    # Stage 2b: optional cross-encoder reranking (retrieve-then-rerank).
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

    # Optional diversity pass (eval-gated): reduce near-duplicate themes at the top.
    if settings.mmr_enabled:
        results = _mmr(filtered, settings.mmr_lambda, limit)
    else:
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
