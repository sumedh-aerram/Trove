"""Learning-to-rank (LTR) reranker: a LightGBM LambdaMART model over the same
hand-crafted features the linear blend uses.

This is a stage-2 reranker that needs no model download and runs in microseconds
(a tree ensemble), unlike a cross-encoder. It is trained and validated by
scripts/train_ltr.py; this module loads the saved model and scores candidates.
Feature extraction lives here so training and serving can never drift apart.

Degrades gracefully: if the model file or lightgbm is missing, callers fall back
to the linear blend.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

# LightGBM and PyTorch both ship an OpenMP runtime; on macOS loading both can
# crash. Allow the duplicate and keep LightGBM single-threaded (predictions are
# tiny, so threading buys nothing and only risks the clash).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from ..utils.dates import recency_score
from .ranking_service import normalize_score, project_relevance_score, substance_score

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parent / "ltr_model.txt"

FEATURE_NAMES = [
    "rel", "rrf_norm", "kw_rank", "vec_sim", "remix", "quality",
    "underground", "recency", "popularity", "substance", "hype", "has_code",
]

_model = None
_load_failed = False


def feature_row(artifact: dict[str, Any], intent: dict[str, Any], rrf_norm: float) -> list[float]:
    """Per-candidate feature vector. MUST match FEATURE_NAMES order and the
    extraction used in scripts/train_ltr.py."""
    kw = float(artifact.get("kw_rank") or 0)
    vec = artifact.get("vec_similarity")
    vec = float(vec) if vec is not None else 0.0
    rel = project_relevance_score(
        artifact, intent,
        kw_rank=kw if kw else None,
        vec_similarity=vec if vec else None,
    )
    return [
        rel,
        rrf_norm,
        kw,
        vec,
        normalize_score(artifact.get("remixability_score")),
        normalize_score(artifact.get("quality_score")),
        normalize_score(artifact.get("underground_score")),
        recency_score(artifact.get("published_at")),
        normalize_score(artifact.get("popularity_score")),
        substance_score(artifact),
        normalize_score(artifact.get("hype_risk_score")),
        1.0 if artifact.get("has_code") else 0.0,
    ]


def _get_model():
    global _model, _load_failed
    if _load_failed:
        return None
    if _model is None:
        if not MODEL_PATH.exists():
            _load_failed = True
            return None
        try:
            import lightgbm as lgb

            _model = lgb.Booster(model_file=str(MODEL_PATH))
        except Exception as exc:  # noqa: BLE001
            logger.warning("LTR model unavailable (%s); using linear blend", exc)
            _load_failed = True
            return None
    return _model


def available() -> bool:
    return _get_model() is not None


def rerank(
    items: list[dict[str, Any]],
    rrf_scores: dict[str, float],
    intent: dict[str, Any],
) -> bool:
    """Score items with the LTR model and set `ltr_score` in place. Returns True
    if applied. Caller re-sorts. rrf_scores maps artifact id -> raw RRF score."""
    model = _get_model()
    if model is None or not items:
        return False
    rows = []
    for a in items:
        rrf_norm = min(1.0, float(rrf_scores.get(str(a["id"]), 0.0)) * 45)
        rows.append(feature_row(a, intent, rrf_norm))
    try:
        scores = model.predict(rows, num_threads=1)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LTR predict failed: %s", exc)
        return False
    for a, s in zip(items, scores):
        a["ltr_score"] = float(s)
    return True


def warmup() -> None:
    _get_model()
