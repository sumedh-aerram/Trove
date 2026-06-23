"""Shared metrics for the frozen curated eval set (used by eval + refresh loop)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from scripts.eval_math import ndcg_at_k, recall_at_k
from scripts.eval_oracle import build_oracle_qrels, gold_pass_at_k
from scripts.eval_queries import EVAL_QUERIES, EVALSET, GOLD_QUERY_INDICES

K = 10
LIMIT = 20
MAX_SINGLE_QUERY_DROP = 0.15
MAX_RECALL_DROP = 0.02


@dataclass
class CuratedEvalReport:
    ndcg: float
    recall: float
    gold_pass_rate: float
    per_query_ndcg: list[float]
    per_query_recall: list[float]
    gold_failures: list[str]

    def regressed_vs(self, before: CuratedEvalReport) -> list[str]:
        reasons: list[str] = []
        if self.ndcg + 1e-6 < before.ndcg:
            reasons.append(f"nDCG@10 dropped ({before.ndcg:.3f} -> {self.ndcg:.3f})")
        if self.recall + MAX_RECALL_DROP < before.recall:
            reasons.append(f"recall@10 dropped ({before.recall:.3f} -> {self.recall:.3f})")
        if self.gold_pass_rate + 1e-6 < before.gold_pass_rate:
            reasons.append(
                f"gold pass rate dropped ({before.gold_pass_rate:.1%} -> {self.gold_pass_rate:.1%})"
            )
        for i, (a, b) in enumerate(zip(before.per_query_ndcg, self.per_query_ndcg)):
            if a - b > MAX_SINGLE_QUERY_DROP:
                reasons.append(
                    f"q{i} '{EVALSET[i][0][:50]}' nDCG dropped {a:.3f} -> {b:.3f}"
                )
        return reasons


async def measure_curated(*, ltr_enabled: bool | None = None) -> CuratedEvalReport:
    """Grade the frozen curated set with the live hybrid pipeline."""
    from app.db import close_pool, init_pool
    from app.services.search_service import hybrid_search

    prev = os.environ.get("LTR_ENABLED")
    if ltr_enabled is not None:
        os.environ["LTR_ENABLED"] = "true" if ltr_enabled else "false"
        from app.config import get_settings

        get_settings.cache_clear()

    await init_pool()
    try:
        qrels, _ = await build_oracle_qrels(EVALSET)
        ndcgs: list[float] = []
        recalls: list[float] = []
        gold_passes = 0
        gold_total = 0
        gold_failures: list[str] = []

        for i, (q, _) in enumerate(EVALSET):
            res = await hybrid_search(q, limit=LIMIT)
            ranked = [str(r["id"]) for r in res["results"]]
            titles = [str(r.get("title") or "") for r in res["results"]]
            qid = f"q{i}"
            ndcgs.append(ndcg_at_k(ranked, qrels[qid]))
            recalls.append(recall_at_k(ranked, qrels[qid]))

            if i in GOLD_QUERY_INDICES:
                gold_total += 1
                hints = EVAL_QUERIES[i].gold_hints
                if gold_pass_at_k(titles, hints, k=5):
                    gold_passes += 1
                else:
                    gold_failures.append(q)

        return CuratedEvalReport(
            ndcg=sum(ndcgs) / len(ndcgs) if ndcgs else 0.0,
            recall=sum(recalls) / len(recalls) if recalls else 0.0,
            gold_pass_rate=(gold_passes / gold_total) if gold_total else 1.0,
            per_query_ndcg=ndcgs,
            per_query_recall=recalls,
            gold_failures=gold_failures,
        )
    finally:
        if ltr_enabled is not None:
            if prev is None:
                os.environ.pop("LTR_ENABLED", None)
            else:
                os.environ["LTR_ENABLED"] = prev
            from app.config import get_settings

            get_settings.cache_clear()
        await close_pool()


def category_means(per_query: list[float]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for i, val in enumerate(per_query):
        cat = EVAL_QUERIES[i].category if i < len(EVAL_QUERIES) else "general"
        buckets.setdefault(cat, []).append(val)
    return {cat: sum(v) / len(v) for cat, v in sorted(buckets.items())}


def worst_queries(per_query_ndcg: list[float], n: int = 5) -> list[tuple[str, float]]:
    indexed = [(EVALSET[i][0], per_query_ndcg[i]) for i in range(len(per_query_ndcg))]
    indexed.sort(key=lambda x: x[1])
    return indexed[:n]
