#!/usr/bin/env python3
"""Eval-driven ranking tuner with nested cross-validation.

Pulls the raw retrieval legs once per query, then re-scores them offline under
many parameter sets (fusion weights, RRF k, gate thresholds, final-score
blend). We use NESTED k-fold CV: for each held-out fold, the best params are
chosen on the other folds and then measured on the held-out queries. That
held-out number is an honest estimate of how the tuning generalizes, instead
of the inflated score you get from tuning and reporting on the same queries.

Run (from apps/api):
  DATABASE_URL=postgresql://postgres:postgres@localhost:5433/build_radar \
    PYTHONPATH=. python scripts/tune_search.py
"""
from __future__ import annotations

import asyncio
import math
import random
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import close_pool, init_pool  # noqa: E402
from app.services.ranking_service import (  # noqa: E402
    normalize_score,
    project_relevance_score,
    substance_score,
)
from app.services.search_service import _dedupe, retrieve_legs  # noqa: E402
from app.utils.dates import recency_score  # noqa: E402
from scripts.eval_search import EVALSET, build_oracle_qrels  # noqa: E402

LIMIT = 20
K = 10
N_SAMPLES = 500
N_FOLDS = 5
SEED = 7


@dataclass
class Params:
    # fusion
    w_kw: float
    w_vec: float
    w_intent: float
    rrf_k: float
    # final-score blend
    rel: float
    rrf: float
    remix: float
    quality: float
    underground: float
    recency: float
    popularity: float
    substance: float
    hype: float
    # gates
    min_final: float
    min_rel: float
    min_vec: float


BASELINE = Params(
    w_kw=1.0, w_vec=0.9, w_intent=0.45, rrf_k=60,
    rel=0.40, rrf=0.10, remix=0.18, quality=0.14, underground=0.08,
    recency=0.08, popularity=0.03, substance=0.12, hype=0.10,
    min_final=0.25, min_rel=0.20, min_vec=0.32,
)


def sample_params(rng: random.Random) -> Params:
    return Params(
        w_kw=rng.uniform(0.4, 1.5),
        w_vec=rng.uniform(0.4, 1.5),
        w_intent=rng.uniform(0.1, 1.0),
        rrf_k=rng.choice([20, 30, 40, 60, 80, 100]),
        rel=rng.uniform(0.2, 0.6),
        rrf=rng.uniform(0.0, 0.4),
        remix=rng.uniform(0.0, 0.3),
        quality=rng.uniform(0.0, 0.3),
        underground=rng.uniform(0.0, 0.2),
        recency=rng.uniform(0.0, 0.2),
        popularity=rng.uniform(0.0, 0.1),
        substance=rng.uniform(0.0, 0.3),
        hype=rng.uniform(0.0, 0.25),
        min_final=rng.uniform(0.0, 0.35),
        min_rel=rng.uniform(0.0, 0.3),
        min_vec=rng.uniform(0.0, 0.45),
    )


def score_query(legs: dict, p: Params) -> list[str]:
    """Re-implement fusion + scoring + gating for one query; return ranked ids."""
    intent = legs["intent"]
    leg_lists = [
        (legs["keyword_hits"], p.w_kw),
        (legs["vector_hits"], p.w_vec),
        (legs["intent_hits"], p.w_intent),
    ]

    rrf: dict[str, float] = {}
    for ranked, weight in leg_lists:
        for rank, item in enumerate(ranked, start=1):
            aid = str(item["id"])
            rrf[aid] = rrf.get(aid, 0.0) + weight * (1.0 / (p.rrf_k + rank))

    by_id: dict[str, dict] = {}
    for ranked, _w in leg_lists:
        for item in ranked:
            aid = str(item["id"])
            if aid not in by_id:
                by_id[aid] = dict(item)
            else:
                cur = by_id[aid]
                if (item.get("kw_rank") or 0) > (cur.get("kw_rank") or 0):
                    cur["kw_rank"] = item["kw_rank"]
                if item.get("vec_similarity") is not None:
                    cur["vec_similarity"] = item.get("vec_similarity")

    scored: list[dict] = []
    for aid, art in by_id.items():
        kw = float(art.get("kw_rank") or 0)
        vec_sim = art.get("vec_similarity")
        rel = project_relevance_score(
            art, intent,
            kw_rank=kw if kw else None,
            vec_similarity=float(vec_sim) if vec_sim is not None else None,
        )
        rrf_norm = min(1.0, rrf.get(aid, 0.0) * 45)
        final = (
            p.rel * rel
            + p.rrf * rrf_norm
            + p.remix * normalize_score(art.get("remixability_score"))
            + p.quality * normalize_score(art.get("quality_score"))
            + p.underground * normalize_score(art.get("underground_score"))
            + p.recency * recency_score(art.get("published_at"))
            + p.popularity * normalize_score(art.get("popularity_score"))
            + p.substance * substance_score(art)
            - p.hype * normalize_score(art.get("hype_risk_score"))
        )
        final = max(0.0, min(1.0, final))
        art["_rel"] = rel
        art["_vec"] = float(vec_sim) if vec_sim is not None else 0.0
        art["_kw"] = kw
        art["final_score"] = final
        scored.append(art)

    gated = [
        a for a in scored
        if a["final_score"] >= p.min_final
        and (a["_rel"] >= p.min_rel or a["_kw"] >= 0.08 or a["_vec"] >= p.min_vec)
    ]
    if len(gated) < min(3, LIMIT) and scored:
        gated = scored[: max(LIMIT, 3)]

    gated = _dedupe(gated)
    gated.sort(key=lambda x: x["final_score"], reverse=True)
    return [str(a["id"]) for a in gated[:LIMIT]]


def ndcg_at_k(ranked_ids: list[str], rels: dict[str, int], k: int = K) -> float:
    """Linear-gain nDCG@k against graded relevance (trec_eval style)."""
    dcg = 0.0
    for i, did in enumerate(ranked_ids[:k]):
        g = rels.get(did, 0)
        if g > 0:
            dcg += g / math.log2(i + 2)
    ideal = sorted(rels.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal) if g > 0)
    return dcg / idcg if idcg > 0 else 0.0


def mean_ndcg(legs_by_q: dict[str, dict], qrels: dict[str, dict[str, int]],
              qids: list[str], p: Params) -> float:
    vals = [ndcg_at_k(score_query(legs_by_q[q], p), qrels[q]) for q in qids]
    return sum(vals) / len(vals) if vals else 0.0


async def main() -> None:
    await init_pool()
    try:
        qrels, _ = await build_oracle_qrels()
        qids = [f"q{i}" for i in range(len(EVALSET))]

        print(f"Pulling retrieval legs for {len(EVALSET)} queries...")
        legs_by_q: dict[str, dict] = {}
        for i, (q, _t) in enumerate(EVALSET):
            legs_by_q[f"q{i}"] = await retrieve_legs(q, candidate_limit=120)

        rng = random.Random(SEED)
        candidates = [BASELINE] + [sample_params(rng) for _ in range(N_SAMPLES)]
        print(f"Scoring {len(candidates)} param sets x {len(qids)} queries...")

        # per-candidate per-query nDCG matrix
        matrix: list[dict[str, float]] = []
        for p in candidates:
            matrix.append({q: ndcg_at_k(score_query(legs_by_q[q], p), qrels[q]) for q in qids})

        base_full = sum(matrix[0].values()) / len(qids)

        # nested CV: pick best on train folds, measure on held-out fold
        rng2 = random.Random(SEED)
        shuffled = qids[:]
        rng2.shuffle(shuffled)
        folds = [shuffled[i::N_FOLDS] for i in range(N_FOLDS)]

        cv_base, cv_tuned = [], []
        for f in range(N_FOLDS):
            test = set(folds[f])
            train = [q for q in qids if q not in test]
            best_ci, best_score = 0, -1.0
            for ci, scores in enumerate(matrix):
                s = sum(scores[q] for q in train) / len(train)
                if s > best_score:
                    best_score, best_ci = s, ci
            test_q = list(test)
            cv_tuned.append(sum(matrix[best_ci][q] for q in test_q) / len(test_q))
            cv_base.append(sum(matrix[0][q] for q in test_q) / len(test_q))

        # best params on the FULL set (what we would ship)
        best_full_ci = max(range(len(candidates)), key=lambda ci: sum(matrix[ci].values()))
        best_full = sum(matrix[best_full_ci].values()) / len(qids)

        print("\n=== Tuning results (nDCG@10, linear-gain) ===")
        print(f"  baseline (current params), full set:   {base_full:.3f}")
        print(f"  best tuned params, full set:           {best_full:.3f}")
        print(f"  nested-CV held-out  baseline:          {sum(cv_base)/N_FOLDS:.3f}")
        print(f"  nested-CV held-out  tuned (honest):    {sum(cv_tuned)/N_FOLDS:.3f}")
        gain = sum(cv_tuned)/N_FOLDS - sum(cv_base)/N_FOLDS
        print(f"  honest generalization gain:            {gain:+.3f}")

        print("\n=== Best params on full set (candidate to ship) ===")
        for k, v in asdict(candidates[best_full_ci]).items():
            print(f"  {k:12s} {v}")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
