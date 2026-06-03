"""Unit tests for GitHub repo -> artifact mapping (no API)."""
from __future__ import annotations

import sys
from pathlib import Path

WORKERS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKERS_ROOT))
sys.path.insert(0, str(WORKERS_ROOT.parent / "apps" / "api"))

from common.github import repo_to_artifact  # noqa: E402
from ingest.run_github import STARTER_QUERIES, build_search_query  # noqa: E402


def test_starter_query_count():
    assert len(STARTER_QUERIES) == 21


def test_build_search_query():
    q = build_search_query("MCP server")
    assert "MCP server" in q
    assert "pushed:>" in q
    assert "stars:<" in q


def test_repo_to_artifact_extraction():
    repo = {
        "full_name": "acme/rag-chrome-ext",
        "html_url": "https://github.com/acme/rag-chrome-ext",
        "description": "RAG Chrome extension for arXiv papers",
        "stargazers_count": 42,
        "forks_count": 3,
        "language": "TypeScript",
        "topics": ["rag", "chrome-extension"],
        "license": {"spdx_id": "MIT"},
        "pushed_at": "2025-05-01T12:00:00Z",
        "owner": {"login": "acme", "html_url": "https://github.com/acme"},
    }
    readme = """# RAG Extension

A Chrome extension that uses retrieval-augmented generation over arXiv PDFs and web pages.
Built with TypeScript, LangChain, and a local vector store for vibe coders.

## Setup
```bash
npm install
pnpm dev
```
"""
    art = repo_to_artifact(repo, readme)
    assert art["source_type"] == "github"
    assert art["canonical_url"]
    assert art["has_code"] is True
    assert art["has_docs"] is True
    assert art["quality_score"] >= 50
    assert "TypeScript" in art["languages"]
    assert art["setup_commands"]
    assert any("npm" in c or "pnpm" in c for c in art["setup_commands"])
