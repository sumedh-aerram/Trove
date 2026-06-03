"""Local SentenceTransformers embeddings (384-dim, no paid LLM)."""
from __future__ import annotations

import logging
from typing import Optional

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
            from sentence_transformers import SentenceTransformer

            settings = get_settings()
            logger.info("Loading embedding model: %s", settings.embedding_model_name)
            _model = SentenceTransformer(settings.embedding_model_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Embedding model unavailable: %s", exc)
            _load_failed = True
            return None
    return _model


def embed_text(text: str) -> Optional[list[float]]:
    """Return a 384-dim embedding vector, or None if the model is unavailable."""
    if not text or not text.strip():
        return None
    model = _get_model()
    if model is None:
        return None
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def warmup() -> None:
    """Eager-load the model at API startup."""
    _get_model()
