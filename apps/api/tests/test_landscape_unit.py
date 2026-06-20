"""Unit tests for landscape query suggestions (no database)."""
from __future__ import annotations

from app.services.landscape_service import _suggest_query


def test_suggest_query_skips_random_language_tags():
    query = "Best way to lower latency for Vision Models"
    intent = {"frameworks": [], "tools": [], "languages": [], "tags": []}
    results = [
        {
            "frameworks": [],
            "tools": [],
            "tags": ["Go", "inference"],
        },
        {
            "frameworks": [],
            "tools": [],
            "tags": ["Go", "vision"],
        },
    ]
    suggestion = _suggest_query(query, intent, results, confidence=55)
    assert "for Go" not in suggestion
    assert suggestion.lower() != query.lower()


def test_suggest_query_prefers_meaningful_goal_tags():
    query = "vision model deployment"
    intent = {"frameworks": [], "tools": [], "languages": [], "tags": []}
    results = [
        {"frameworks": [], "tools": [], "tags": ["edge", "inference"]},
        {"frameworks": [], "tools": [], "tags": ["edge", "on-device"]},
        {"frameworks": [], "tools": [], "tags": ["edge"]},
    ]
    suggestion = _suggest_query(query, intent, results, confidence=48)
    assert suggestion
    assert "edge" in suggestion.lower()


def test_suggest_query_adds_stack_when_results_agree():
    query = "RAG chat app"
    intent = {"frameworks": [], "tools": [], "languages": [], "tags": []}
    results = [
        {"frameworks": ["LangChain"], "tools": [], "tags": ["rag"]},
        {"frameworks": ["LangChain"], "tools": ["Chroma"], "tags": ["rag"]},
    ]
    suggestion = _suggest_query(query, intent, results, confidence=40)
    assert "LangChain" in suggestion


def test_suggest_query_empty_when_already_specific():
    query = "Best way to lower latency for Vision Models on edge devices"
    intent = {"frameworks": [], "tools": [], "languages": [], "tags": []}
    results = [
        {"frameworks": [], "tools": [], "tags": ["Go"]},
        {"frameworks": [], "tools": [], "tags": ["Go"]},
    ]
    suggestion = _suggest_query(query, intent, results, confidence=55)
    assert suggestion == ""
