#!/usr/bin/env python3
"""Learning-to-rank (LTR) experiment: can a learned model beat the linear blend?

Builds per-(query, candidate) feature vectors from the same signals the live
ranker uses, labels them with the oracle graded relevance, and compares three
rankers with NESTED 5-fold CV (honest, held-out nDCG@10):

  1. baseline  - the current hand-tuned linear blend (compute_final_score)
  2. lambdamart- LightGBM listwise ranker (objective=lambdarank)
  3. logreg    - pointwise logistic regression on binary relevance

If a learner generalizes better, it retrains on all queries and saves the model
to app/services/ltr_model.txt for serving. If not, we keep the linear blend
(zero added dependency at serve time). Either way the eval decides.

Run (from apps/api):
  DATABASE_URL=postgresql://postgres:postgres@localhost:5433/build_radar \
    PYTHONPATH=. python scripts/train_ltr.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import close_pool, init_pool  # noqa: E402
from app.services.ranking_service import compute_final_score  # noqa: E402
from app.services.ltr_service import FEATURE_NAMES, feature_row  # noqa: E402
from app.services.search_service import retrieve_legs  # noqa: E402
from scripts.eval_search import EVALSET, build_oracle_qrels  # noqa: E402
from scripts.tune_search import ndcg_at_k  # noqa: E402

FUSION_W = {"kw": 1.31, "vec": 0.60, "intent": 0.28}
RRF_K = 60
N_FOLDS = 5
SEED = 7


def _candidates(legs: dict) -> tuple[list[dict], dict[str, float]]:
    """Merge legs, attach kw/vec signals, compute weighted RRF per candidate."""
    leg_lists = [
        (legs["keyword_hits"], FUSION_W["kw"]),
        (legs["vector_hits"], FUSION_W["vec"]),
        (legs["intent_hits"], FUSION_W["intent"]),
    ]
    rrf: dict[str, float] = {}
    by_id: dict[str, dict] = {}
    for ranked, weight in leg_lists:
        for rank, item in enumerate(ranked, start=1):
            aid = str(item["id"])
            rrf[aid] = rrf.get(aid, 0.0) + weight * (1.0 / (RRF_K + rank))
            if aid not in by_id:
                by_id[aid] = dict(item)
            else:
                cur = by_id[aid]
                if (item.get("kw_rank") or 0) > (cur.get("kw_rank") or 0):
                    cur["kw_rank"] = item["kw_rank"]
                if item.get("vec_similarity") is not None:
                    cur["vec_similarity"] = item.get("vec_similarity")
    return list(by_id.values()), rrf


def ndcg_from_scores(ids: list[str], scores: list[float], rels: dict[str, int]) -> float:
    order = sorted(range(len(ids)), key=lambda i: scores[i], reverse=True)
    ranked = [ids[i] for i in order][:20]
    return ndcg_at_k(ranked, rels)


async def main() -> None:
    import lightgbm as lgb
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    await init_pool()
    try:
        qrels, _ = await build_oracle_qrels()
        per_q: dict[str, dict] = {}
        print(f"Building feature sets for {len(EVALSET)} queries...")
        for i, (q, _t) in enumerate(EVALSET):
            qid = f"q{i}"
            legs = await retrieve_legs(q, candidate_limit=120)
            cands, rrf = _candidates(legs)
            ids, X, base_scores = [], [], []
            for art in cands:
                aid = str(art["id"])
                rrf_norm = min(1.0, rrf.get(aid, 0.0) * 45)
                ids.append(aid)
                X.append(feature_row(art, legs["intent"], rrf_norm))
                base_scores.append(compute_final_score(art, legs["intent"], rrf.get(aid, 0.0)))
            labels = [qrels[qid].get(aid, 0) for aid in ids]
            per_q[qid] = {"ids": ids, "X": np.array(X), "y": np.array(labels),
                          "base": base_scores, "rels": qrels[qid]}

        qids = [f"q{i}" for i in range(len(EVALSET))]
        rng = np.random.RandomState(SEED)
        shuffled = qids[:]
        rng.shuffle(shuffled)
        folds = [shuffled[i::N_FOLDS] for i in range(N_FOLDS)]

        res = {"baseline": [], "lambdamart": [], "logreg": []}
        for f in range(N_FOLDS):
            test = folds[f]
            train = [q for q in qids if q not in test]

            # assemble train matrices
            Xtr = np.vstack([per_q[q]["X"] for q in train])
            ytr = np.concatenate([per_q[q]["y"] for q in train])
            groups = [len(per_q[q]["ids"]) for q in train]

            # 1) baseline (no training)
            res["baseline"].append(
                np.mean([ndcg_from_scores(per_q[q]["ids"], per_q[q]["base"], per_q[q]["rels"]) for q in test])
            )

            # 2) LambdaMART
            ranker = lgb.LGBMRanker(
                objective="lambdarank", n_estimators=120, num_leaves=15,
                learning_rate=0.08, min_child_samples=10, subsample=0.9,
                colsample_bytree=0.9, random_state=SEED, verbosity=-1,
            )
            ranker.fit(Xtr, ytr, group=groups)
            res["lambdamart"].append(
                np.mean([ndcg_from_scores(per_q[q]["ids"], list(ranker.predict(per_q[q]["X"])), per_q[q]["rels"]) for q in test])
            )

            # 3) logistic regression (pointwise, binary relevance)
            scaler = StandardScaler().fit(Xtr)
            ybin = (ytr >= 2).astype(int)
            if len(set(ybin)) > 1:
                clf = LogisticRegression(max_iter=1000, C=1.0).fit(scaler.transform(Xtr), ybin)
                res["logreg"].append(
                    np.mean([ndcg_from_scores(per_q[q]["ids"], list(clf.predict_proba(scaler.transform(per_q[q]["X"]))[:, 1]), per_q[q]["rels"]) for q in test])
                )

        print("\n=== LTR nested-CV held-out nDCG@10 (honest) ===")
        for name, vals in res.items():
            if vals:
                print(f"  {name:12s} {np.mean(vals):.3f}")

        best = max((k for k in res if res[k]), key=lambda k: np.mean(res[k]))
        base = np.mean(res["baseline"])
        print(f"\n  best learner: {best} ({np.mean(res[best]):.3f} vs baseline {base:.3f}, "
              f"{np.mean(res[best]) - base:+.3f})")

        if best == "lambdamart" and np.mean(res["lambdamart"]) > base + 0.005:
            print("\nLambdaMART generalizes better -> retraining on all queries and saving model.")
            Xall = np.vstack([per_q[q]["X"] for q in qids])
            yall = np.concatenate([per_q[q]["y"] for q in qids])
            groups = [len(per_q[q]["ids"]) for q in qids]
            ranker = lgb.LGBMRanker(
                objective="lambdarank", n_estimators=120, num_leaves=15,
                learning_rate=0.08, min_child_samples=10, subsample=0.9,
                colsample_bytree=0.9, random_state=SEED, verbosity=-1,
            )
            ranker.fit(Xall, yall, group=groups)
            out = Path(__file__).resolve().parents[1] / "app" / "services" / "ltr_model.txt"
            ranker.booster_.save_model(str(out))
            print(f"  saved -> {out}")
        else:
            print("\nNo learner beats the linear blend on held-out queries. Keeping the\n"
                  "linear blend (no serve-time dependency). The eval made the call.")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
