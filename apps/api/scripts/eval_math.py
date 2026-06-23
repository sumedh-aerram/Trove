"""Shared ranking metrics for eval scripts (no heavy imports)."""
from __future__ import annotations

import math

K = 10


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


def recall_at_k(ranked_ids: list[str], rels: dict[str, int], k: int = K) -> float:
    rel_ids = {did for did, g in rels.items() if g > 0}
    if not rel_ids:
        return 1.0
    hits = sum(1 for did in ranked_ids[:k] if did in rel_ids)
    return hits / min(len(rel_ids), k)
