"""Relevance + quality gating shared by all crawlers.

Goal: only index artifacts that actually pertain to the crawl query, and skip
low-signal junk early so we never waste latency embedding or storing it.

Two layers:
  1. Cheap heuristic gates (no model needed) -> filter obvious noise fast.
  2. Semantic relevance: cosine(query_embedding, artifact_embedding).

Both degrade gracefully: if embeddings are unavailable, only heuristics apply.
"""
from __future__ import annotations

import math
import os
from typing import Any, Optional, Sequence

from .paths import *  # noqa: F403  (puts apps/api on sys.path before app imports)

from app.services.embedding_service import embed_text  # noqa: E402

# Cosine threshold on normalized MiniLM vectors. Related builds typically score
# 0.20-0.55; unrelated noise sits below ~0.12. Raised from 0.16 to trim the
# low-signal long tail (mostly Hacker News link posts) that hurt perceived
# relevance. Tunable via env.
RELEVANCE_MIN = float(os.getenv("CRAWL_RELEVANCE_MIN", "0.22"))
MIN_TEXT_LEN = int(os.getenv("CRAWL_MIN_TEXT_LEN", "60"))

# Titles that are almost always noise for a "what can I build" index.
_NOISE_TITLE_HINTS = (
    "test", "demo-repo", "hello-world", "my-portfolio", "config", "dotfiles",
    "interview", "leetcode", "assignment", "homework", "tutorial-",
    "awesome-", "cheatsheet", "cheat-sheet", "roadmap", "course", "bootcamp",
    "interview-questions", "study-notes", "list of",
)


def cosine(a: Sequence[float] | None, b: Sequence[float] | None) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def embed_query(query: str) -> Optional[list[float]]:
    """Embed the crawl query once per run; reuse across candidates."""
    return embed_text(query)


def _signal_text(artifact: dict[str, Any]) -> str:
    return " ".join(
        str(artifact.get(k) or "")
        for k in ("title", "summary", "what_it_helps_build", "technical_core")
    ).strip()


def heuristic_quality_ok(artifact: dict[str, Any]) -> bool:
    """Fast, model-free gate. Returns False for obvious low-signal noise."""
    text = _signal_text(artifact)
    if len(text) < MIN_TEXT_LEN:
        return False

    title = (artifact.get("title") or "").lower()
    if any(hint in title for hint in _NOISE_TITLE_HINTS):
        return False

    # Needs at least some structured signal: stack, tags, or code.
    has_stack = any(
        artifact.get(k) for k in ("frameworks", "tools", "languages", "tags")
    )
    if not has_stack and not artifact.get("has_code"):
        return False
    return True


def relevance_ok(
    artifact: dict[str, Any],
    query_embedding: Optional[Sequence[float]],
    *,
    threshold: float = RELEVANCE_MIN,
) -> tuple[bool, float]:
    """Semantic gate. If no embeddings available, pass (heuristics already ran)."""
    art_vec = artifact.get("embedding_vector")
    if not query_embedding or not art_vec:
        return True, 0.0
    score = cosine(query_embedding, art_vec)
    return score >= threshold, score


def passes(
    artifact: dict[str, Any],
    query_embedding: Optional[Sequence[float]],
    *,
    threshold: float = RELEVANCE_MIN,
) -> tuple[bool, float]:
    """Combined gate used by crawlers."""
    if not heuristic_quality_ok(artifact):
        return False, 0.0
    return relevance_ok(artifact, query_embedding, threshold=threshold)
