"""Stage-2 cross-encoder reranking.

First-stage hybrid retrieval (FTS + pgvector + RRF) is recall-oriented and cheap.
This second stage takes the top candidates and rescoring them with a cross-encoder
that reads the (query, document) pair jointly — far more precise than bi-encoder
cosine — then the caller blends that into the final score.

Retrieve-then-rerank is the standard modern search / RAG ranking pattern.
Degrades gracefully: if the model can't load, candidates are returned unchanged.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Optional

from ..config import get_settings

logger = logging.getLogger(__name__)

_model = None
_load_failed = False


def _get_model():
    global _model, _load_failed
    if _load_failed:
        return None
    if _model is None:
        try:
            from sentence_transformers import CrossEncoder

            settings = get_settings()
            logger.info("Loading cross-encoder reranker: %s", settings.rerank_model)
            _model = CrossEncoder(settings.rerank_model, max_length=384)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Reranker unavailable (%s); skipping stage-2 rerank", exc)
            _load_failed = True
            return None
    return _model


def _doc_text(a: dict[str, Any]) -> str:
    parts = [
        a.get("title") or "",
        a.get("summary") or "",
        a.get("what_it_helps_build") or "",
        " ".join(a.get("tags") or []),
        " ".join(a.get("frameworks") or []),
        " ".join(a.get("tools") or []),
    ]
    return " ".join(p for p in parts if p)[:600]


def rerank(query: str, items: list[dict[str, Any]], top_k: int) -> bool:
    """Set `rerank_score` (0-1) on the top_k items in place. Returns True if applied."""
    model = _get_model()
    if model is None or not items:
        return False

    head = items[:top_k]
    pairs = [(query, _doc_text(a)) for a in head]
    try:
        scores = model.predict(pairs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rerank predict failed: %s", exc)
        return False

    for a, s in zip(head, scores):
        # ms-marco cross-encoders emit a logit; squash to 0-1.
        a["rerank_score"] = 1.0 / (1.0 + math.exp(-float(s)))
    return True


def warmup() -> None:
    if get_settings().rerank_enabled:
        _get_model()
