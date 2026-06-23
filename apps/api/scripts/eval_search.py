#!/usr/bin/env python3
"""Retrieval eval harness using ranx (trec_eval-validated metrics).

Compares ranking configs on nDCG@10, MRR, Recall@10, MAP with bootstrap CIs,
category breakdown, gold-subset checks, and retrieval-vs-ranking diagnostics.

Run (from apps/api):
  DATABASE_URL=postgresql://postgres:postgres@localhost:5433/build_radar \
    PYTHONPATH=. python scripts/eval_search.py

  # Leakage-free retrieval benchmark (no learned reranker):
  LTR_ENABLED=false PYTHONPATH=. python scripts/eval_search.py
"""
from __future__ import annotations

import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import close_pool, init_pool  # noqa: E402
from app.services.search_service import hybrid_search  # noqa: E402
from scripts.eval_math import ndcg_at_k, recall_at_k
from scripts.eval_oracle import build_oracle_qrels, gold_pass_at_k
from scripts.eval_queries import EVALSET, EVAL_QUERIES, GOLD_QUERY_INDICES
__all__ = ["EVALSET", "build_oracle_qrels"]

K = 10
LIMIT = 20
BOOTSTRAP_ITERS = 2000


def bootstrap_ci(per_query: list[float], iters: int = BOOTSTRAP_ITERS) -> tuple[float, float, float]:
    n = len(per_query)
    if n == 0:
        return 0.0, 0.0, 0.0
    rng = random.Random(13)
    means = []
    for _ in range(iters):
        sample = [per_query[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * iters)]
    hi = means[int(0.975 * iters)]
    return sum(per_query) / n, lo, hi


async def run() -> None:
    from ranx import Qrels, Run, compare, evaluate

    from scripts.eval_metrics import category_means, measure_curated, worst_queries

    await init_pool()
    configs = {"stage-1 hybrid": False, "stage-2 +rerank": True}
    runs: dict[str, dict[str, dict[str, float]]] = {name: {} for name in configs}
    pool_recall: dict[str, list[float]] = {name: [] for name in configs}
    top_recall: dict[str, list[float]] = {name: [] for name in configs}
    per_q_ndcg: dict[str, list[float]] = {name: [] for name in configs}
    gold_pass: dict[str, list[bool]] = {name: [] for name in configs}

    try:
        qrels_dict, relevant_ids = await build_oracle_qrels(write_snapshot=True)

        for qi, (q, _terms) in enumerate(EVALSET):
            qid = f"q{qi}"
            rel = relevant_ids[qid]
            for name, rerank in configs.items():
                res = await hybrid_search(q, limit=LIMIT, rerank=rerank)
                results = res["results"]
                scores: dict[str, float] = {}
                returned_ids: list[str] = []
                titles: list[str] = []
                for rank, r in enumerate(results):
                    did = str(r["id"])
                    returned_ids.append(did)
                    titles.append(str(r.get("title") or ""))
                    scores[did] = float(r.get("final_score") or 0) + (LIMIT - rank) * 1e-6
                runs[name][qid] = scores
                per_q_ndcg[name].append(ndcg_at_k(returned_ids, qrels_dict[qid]))
                if rel:
                    found = sum(1 for d in returned_ids if d in rel)
                    in_top = sum(1 for d in returned_ids[:K] if d in rel)
                    denom = min(len(rel), LIMIT)
                    pool_recall[name].append(found / denom)
                    top_recall[name].append(in_top / min(len(rel), K))
                if qi in GOLD_QUERY_INDICES:
                    gold_pass[name].append(
                        gold_pass_at_k(titles, EVAL_QUERIES[qi].gold_hints, k=5)
                    )

        qrels = Qrels(qrels_dict)
        run_objs = [Run(runs[name], name=name) for name in configs]

        print(f"\n=== Trove retrieval eval (ranx, {len(EVALSET)} queries, weighted oracle) ===\n")
        report = compare(
            qrels=qrels,
            runs=run_objs,
            metrics=["ndcg@10", "mrr", "recall@10", "map@10"],
            max_p=0.05,
        )
        print(report)

        print("\n--- nDCG@10 with 95% bootstrap CI ---")
        for name in configs:
            per_q = list(evaluate(qrels, run_objs[list(configs).index(name)], "ndcg@10", return_mean=False))
            mean, lo, hi = bootstrap_ci(per_q)
            print(f"  {name:18s} {mean:.3f}  [{lo:.3f}, {hi:.3f}]")

        print("\n--- category breakdown (nDCG@10, stage-1) ---")
        for cat, mean in category_means(per_q_ndcg["stage-1 hybrid"]).items():
            print(f"  {cat:16s} {mean:.3f}")

        print("\n--- gold subset (title-hint pass@5) ---")
        for name in configs:
            gp = gold_pass[name]
            rate = sum(gp) / len(gp) if gp else 1.0
            print(f"  {name:18s} {rate:.1%}  ({sum(gp)}/{len(gp)} queries)")

        print("\n--- weakest queries (stage-1 nDCG@10) ---")
        for q, score in worst_queries(per_q_ndcg["stage-1 hybrid"], n=5):
            print(f"  {score:.3f}  {q[:70]}")

        print("\n--- diagnostics: retrieval vs ranking ---")
        print(f"  {'config':18s} {'pool_recall@20':>14s} {'top_recall@10':>14s}")
        for name in configs:
            pr = sum(pool_recall[name]) / len(pool_recall[name]) if pool_recall[name] else 0.0
            tr = sum(top_recall[name]) / len(top_recall[name]) if top_recall[name] else 0.0
            print(f"  {name:18s} {pr:>14.3f} {tr:>14.3f}")
        print(
            "\n  pool_recall@20 = relevant docs surfaced anywhere in results.\n"
            "  top_recall@10  = relevant docs in top 10.\n"
            "  Low pool => fix retrieval. High pool, low top => fix ranking."
        )

        from app.config import get_settings

        if get_settings().ltr_enabled:
            print(
                "\n  !!! LTR ENABLED: in-sample bias possible. For leakage-free\n"
                "  numbers run: LTR_ENABLED=false python scripts/eval_search.py"
            )

        print("\n--- retrieval-only pass (LTR off) ---")
        retrieval_report = await measure_curated(ltr_enabled=False)
        print(
            f"  nDCG@10 {retrieval_report.ndcg:.3f}  "
            f"recall@10 {retrieval_report.recall:.3f}  "
            f"gold {retrieval_report.gold_pass_rate:.1%}"
        )
        if retrieval_report.gold_failures:
            print("  gold failures:")
            for q in retrieval_report.gold_failures[:5]:
                print(f"    - {q[:70]}")

        print(f"\n  qrels snapshot -> eval/qrels_snapshot.json")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(run())
