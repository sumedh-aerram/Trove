"""Unit tests for intent extraction and why_relevant (no database)."""
from __future__ import annotations

from app.services.extraction_service import extract_project_intent
from app.services.intent_retrieval import build_retrieval_context, enrich_intent
from app.services.ranking_service import build_why_relevant, project_relevance_score


RAG_CHROME_QUERY = (
    "I'm building a RAG Chrome extension that explains research papers. "
    "I need open-source repos, architecture ideas, and useful libraries."
)

PAPERPAL_ARTIFACT = {
    "id": "00000000-0000-0000-0000-000000000001",
    "title": "paperpal/rag-chrome-extension",
    "summary": "Chrome extension boilerplate that explains pages and PDFs using RAG.",
    "artifact_type": "starter_template",
    "tags": ["rag", "extension", "browser", "pdf"],
    "tools": ["LangChain", "Chroma"],
    "frameworks": ["Chrome Extension", "React"],
    "languages": ["TypeScript"],
    "has_code": True,
    "setup_commands": ["npm install"],
}


def test_rag_chrome_intent_project_type():
    intent = enrich_intent(RAG_CHROME_QUERY, extract_project_intent(RAG_CHROME_QUERY))
    assert intent["project_type"] == "rag_browser_research"
    assert "rag" in intent["search_terms"]
    assert "chrome" in intent["search_terms"] or "extension" in intent["search_terms"]


def test_retrieval_context_includes_stack():
    intent = enrich_intent(RAG_CHROME_QUERY, extract_project_intent(RAG_CHROME_QUERY))
    ctx = build_retrieval_context(RAG_CHROME_QUERY, intent)
    assert "Chrome" in ctx or "extension" in ctx.lower()
    assert "rag" in ctx.lower() or "RAG" in ctx


def test_why_relevant_rag_chrome_narrative():
    intent = enrich_intent(RAG_CHROME_QUERY, extract_project_intent(RAG_CHROME_QUERY))
    why = build_why_relevant(PAPERPAL_ARTIFACT, intent)
    assert "browser extension" in why.lower()
    assert "rag" in why.lower()
    assert "research paper" in why.lower() or "paper" in why.lower()


def test_project_relevance_high_for_matching_artifact():
    intent = enrich_intent(RAG_CHROME_QUERY, extract_project_intent(RAG_CHROME_QUERY))
    score = project_relevance_score(PAPERPAL_ARTIFACT, intent, kw_rank=0.15)
    assert score >= 0.45


def test_lecture_intent_terms():
    q = "AI lecture summarizer with quiz generation"
    intent = enrich_intent(q, extract_project_intent(q))
    assert intent["project_type"] == "education_media"
    terms = " ".join(intent["search_terms"])
    assert "lecture" in terms or "quiz" in terms or "summarizer" in terms
