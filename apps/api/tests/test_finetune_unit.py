"""Unit tests for embedding fine-tune data assembly (no database)."""
from __future__ import annotations

from scripts.eval_data import merge_training_pairs


def test_merge_training_pairs_dedupes_and_prefers_feedback_order():
    feedback = [{"query": "RAG app", "positive_id": "a", "kind": "click"}]
    curated = [
        {"query": "RAG app", "positive_id": "a", "kind": "curated"},
        {"query": "MCP server", "positive_id": "b", "kind": "curated"},
    ]
    merged = merge_training_pairs(feedback, curated)
    assert len(merged) == 2
    assert merged[0]["kind"] == "click"
    assert {p["positive_id"] for p in merged} == {"a", "b"}


def test_merge_training_pairs_case_insensitive_query():
    feedback = [{"query": "RAG App", "positive_id": "a", "kind": "click"}]
    curated = [{"query": "rag app", "positive_id": "b", "kind": "curated"}]
    merged = merge_training_pairs(feedback, curated)
    assert len(merged) == 2
