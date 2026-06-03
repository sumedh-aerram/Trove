"""Integration tests for hybrid search (requires Postgres + seed data)."""
from __future__ import annotations

import os

import pytest
import pytest_asyncio

from app.db import close_pool, init_pool
from app.services.search_service import hybrid_search

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


@pytest_asyncio.fixture
async def _db():
    await init_pool()
    yield
    await close_pool()


def _titles(results: list[dict]) -> str:
    return " ".join(r.get("title", "").lower() for r in results)


def _blob(results: list[dict]) -> str:
    parts = []
    for r in results:
        parts.append(r.get("title", ""))
        parts.append(r.get("summary", ""))
        parts.append(" ".join(r.get("tags") or []))
    return " ".join(parts).lower()


@pytest.mark.asyncio
async def test_lecture_summarizer_search(_db):
    out = await hybrid_search("AI lecture summarizer", limit=10)
    assert out["total"] >= 1
    blob = _blob(out["results"])
    assert any(k in blob for k in ("lecture", "quiz", "summarizer", "whisper", "flashcard", "video"))


@pytest.mark.asyncio
async def test_rag_chrome_extension_search(_db):
    out = await hybrid_search("RAG Chrome extension", limit=10)
    assert out["total"] >= 1
    titles = _titles(out["results"])
    assert "rag" in titles or "chrome" in titles or "extension" in titles
    assert any(
        k in _blob(out["results"])
        for k in ("rag", "chrome", "extension", "pdf", "browser")
    )


@pytest.mark.asyncio
async def test_rag_chrome_full_context_query(_db):
    q = (
        "I'm building a RAG Chrome extension that explains research papers. "
        "I need open-source repos, architecture ideas, and useful libraries."
    )
    out = await hybrid_search(q, limit=5)
    assert out["intent"]["project_type"] == "rag_browser_research"
    assert out["total"] >= 1
    top = out["results"][0]
    assert top.get("why_relevant")
    blob = (top.get("title", "") + top.get("summary", "")).lower()
    assert "rag" in blob or "rag" in " ".join(top.get("tags") or []).lower()
    # paperpal seed should rank highly.
    assert "paperpal" in _titles(out["results"][:3]) or "rag-chrome" in _titles(out["results"][:3])


@pytest.mark.asyncio
async def test_mcp_coding_agent_search(_db):
    out = await hybrid_search("MCP server for coding agents", limit=10)
    blob = _blob(out["results"])
    assert "mcp" in blob or "coding" in blob or "agent" in blob


@pytest.mark.asyncio
async def test_computer_vision_posture_search(_db):
    out = await hybrid_search("computer vision posture app", limit=10)
    blob = _blob(out["results"])
    assert any(k in blob for k in ("vision", "posture", "pose", "mediapipe", "hack-health"))


@pytest.mark.asyncio
async def test_filters_artifact_type(_db):
    out = await hybrid_search(
        "MCP server",
        limit=10,
        filters={"artifact_type": "mcp_server"},
    )
    for r in out["results"]:
        assert r["artifact_type"] == "mcp_server"


@pytest.mark.asyncio
async def test_filters_min_quality(_db):
    out = await hybrid_search(
        "starter template",
        limit=10,
        filters={"min_quality_score": 75},
    )
    for r in out["results"]:
        assert float(r.get("quality_score") or 0) >= 75
