"""Unit tests for eval oracle grading (no database)."""
from __future__ import annotations

from scripts.eval_oracle import (
    MIN_GRADE_POINTS,
    expand_terms,
    gold_pass_at_k,
    grade_row,
    title_matches_hints,
)


def test_expand_terms_adds_synonyms():
    terms = expand_terms(["llm", "mcp"])
    assert "language model" in terms
    assert "model context protocol" in terms


def test_grade_row_title_weighted_higher():
    row = {
        "title": "awesome-mcp-server for Cursor agents",
        "summary": "generic dev tool",
        "tags": [],
        "tools": [],
        "frameworks": [],
        "languages": [],
    }
    score = grade_row(row, ["mcp", "agent"])
    assert score >= MIN_GRADE_POINTS


def test_gold_pass_at_k():
    titles = ["random repo", "my-mcp-bridge", "other"]
    assert gold_pass_at_k(titles, ("mcp",), k=5)
    assert not gold_pass_at_k(["foo", "bar"], ("mcp",), k=5)


def test_title_matches_hints_case_insensitive():
    assert title_matches_hints("Foo-MCP-Bar", ("mcp",))
