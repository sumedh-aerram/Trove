"""Build FTS and embedding text from project-context queries + intent."""
from __future__ import annotations

import re
from typing import Any

from ..utils.text import dedupe_keep_order

# English stopwords (common in project-context queries).
_STOPWORDS = frozenset(
    """
    a an the and or but in on at to for of with by from as is are was were be been
    being have has had do does did will would could should may might must can i im
    me my we our you your they them their it its this that these those what which
    who how when where why all any both each few more most other some such no nor
    not only own same so than too very just also need needs want show find get use
    using build building into about over under between through during before after
    above below up down out off again further then once here there when all both
    """.split()
)

# Maps project_type -> extra retrieval terms and ranking hints.
_PROJECT_PROFILES: dict[str, dict[str, list[str]]] = {
    "rag_browser_research": {
        "tags": ["rag", "retrieval", "extension", "browser", "chrome", "arxiv", "pdf", "paper", "research"],
        "tools": ["LangChain", "LlamaIndex", "pgvector", "Chroma"],
        "frameworks": ["Chrome Extension", "React", "Next.js", "TypeScript"],
        "languages": ["TypeScript", "JavaScript"],
        "search_terms": [
            "rag", "chrome", "extension", "browser", "arxiv", "pdf", "paper",
            "research", "summarizer", "retrieval", "vector",
        ],
    },
    "education_media": {
        "tags": ["lecture", "video", "quiz", "flashcards", "summarizer", "transcription", "education"],
        "tools": ["Whisper", "ffmpeg", "Supabase"],
        "frameworks": ["Next.js"],
        "search_terms": ["lecture", "summarizer", "quiz", "video", "whisper", "flashcard", "transcription"],
    },
    "coding_agent_tooling": {
        "tags": ["mcp", "coding-agent", "cursor", "claude", "workflow", "agent"],
        "tools": ["MCP", "Claude Code", "Cursor"],
        "search_terms": ["mcp", "coding", "agent", "cursor", "claude", "workflow", "server"],
    },
    "computer_vision": {
        "tags": ["computer-vision", "pose", "posture", "webcam", "hackathon", "mediapipe"],
        "tools": ["MediaPipe"],
        "search_terms": ["computer", "vision", "pose", "posture", "webcam", "hackathon", "opencv"],
    },
    "browser_extension": {
        "tags": ["extension", "browser", "chrome", "frontend"],
        "frameworks": ["Chrome Extension"],
        "search_terms": ["chrome", "extension", "browser"],
    },
    "rag_research": {
        "tags": ["rag", "retrieval", "arxiv", "paper", "vector"],
        "tools": ["LangChain", "pgvector"],
        "search_terms": ["rag", "retrieval", "arxiv", "paper", "vector", "embedding"],
    },
}


def detect_project_type(lower: str) -> str:
    """Score composite project types for long context queries."""
    scores: dict[str, float] = {}

    def bump(name: str, amount: float) -> None:
        scores[name] = scores.get(name, 0.0) + amount

    has_rag = any(x in lower for x in ("rag", "retrieval", "retrieval-augmented", "vector"))
    has_browser = any(x in lower for x in ("chrome", "browser extension", "extension"))
    has_paper = any(x in lower for x in ("paper", "papers", "arxiv", "pdf", "research"))
    has_lecture = any(x in lower for x in ("lecture", "quiz", "flashcard", "video summarizer"))
    has_mcp = any(x in lower for x in ("mcp", "coding agent", "claude code", "cursor"))
    has_cv = any(x in lower for x in ("computer vision", "posture", "pose", "webcam"))

    if has_rag and has_browser and has_paper:
        bump("rag_browser_research", 10)
    if has_rag and has_browser:
        bump("rag_browser_research", 5)
    if has_lecture:
        bump("education_media", 8)
    if has_mcp:
        bump("coding_agent_tooling", 8)
    if has_cv:
        bump("computer_vision", 8)
    if has_rag and has_paper and not has_browser:
        bump("rag_research", 6)
    if has_browser and not has_rag:
        bump("browser_extension", 4)

    if not scores:
        return "general"
    return max(scores, key=scores.get)


def extract_significant_terms(query: str, max_terms: int = 20) -> list[str]:
    """Tokenize query; drop stopwords; keep meaningful terms."""
    raw = re.findall(r"[a-zA-Z][a-zA-Z0-9+.#-]*|[0-9]+[a-zA-Z]*", query.lower())
    terms: list[str] = []
    for tok in raw:
        if tok in _STOPWORDS or len(tok) < 3:
            continue
        terms.append(tok)
    return dedupe_keep_order(terms)[:max_terms]


def enrich_intent(query: str, intent: dict[str, Any]) -> dict[str, Any]:
    """Attach retrieval terms and profile expansions to intent."""
    lower = query.lower()
    project_type = detect_project_type(lower)
    intent = {**intent, "project_type": project_type}

    profile = _PROJECT_PROFILES.get(project_type, {})
    for key in ("tags", "tools", "frameworks", "languages", "search_terms"):
        if key in profile:
            existing = intent.get(key if key != "search_terms" else "tags", [])
            if key == "search_terms":
                intent["search_terms"] = dedupe_keep_order(
                    list(intent.get("search_terms", [])) + profile["search_terms"]
                )
            else:
                intent[key] = dedupe_keep_order(list(existing) + profile[key])

    intent["search_terms"] = dedupe_keep_order(
        list(intent.get("search_terms", []))
        + extract_significant_terms(query)
        + [t.lower() for t in intent.get("tags", [])]
        + [t.lower() for t in intent.get("tools", [])]
        + [t.lower().replace(" ", "") for t in intent.get("frameworks", [])]
    )

    # Phrase-level expansions for long queries.
    if "open source" in lower or "open-source" in lower or "repos" in lower:
        intent.setdefault("desired_artifact_types", [])
        if "open_source_project" not in intent["desired_artifact_types"]:
            intent["desired_artifact_types"].insert(0, "open_source_project")
        intent["search_terms"].extend(["open", "source", "repository", "repo"])

    if "architecture" in lower:
        intent["search_terms"].extend(["architecture", "pattern", "stack"])

    if "libraries" in lower or "library" in lower:
        intent["search_terms"].extend(["library", "sdk", "package"])

    if "pdf" in lower:
        intent["search_terms"].extend(["pdf", "document", "parser"])

    intent["search_terms"] = dedupe_keep_order(intent["search_terms"])[:30]
    return intent


def build_retrieval_context(query: str, intent: dict[str, Any]) -> str:
    """Rich text for embedding — captures project context, not just keywords."""
    focus = str(intent.get("project_type", "general")).replace("_", " ")
    lines = [
        query.strip(),
        "Builder search: open-source projects, techniques, starter templates, MCP servers, and papers.",
        f"Project focus: {focus}.",
    ]
    if intent.get("frameworks"):
        lines.append("Frameworks: " + ", ".join(intent["frameworks"]) + ".")
    if intent.get("tools"):
        lines.append("Tools: " + ", ".join(intent["tools"]) + ".")
    if intent.get("languages"):
        lines.append("Languages: " + ", ".join(intent["languages"]) + ".")
    if intent.get("tags"):
        lines.append("Topics: " + ", ".join(intent["tags"]) + ".")
    if intent.get("models"):
        lines.append("Models: " + ", ".join(intent["models"]) + ".")
    types = intent.get("desired_artifact_types") or []
    if types:
        lines.append("Looking for: " + ", ".join(t.replace("_", " ") for t in types[:6]) + ".")
    return "\n".join(lines)


def build_fts_or_query(intent: dict[str, Any]) -> str:
    """Build a PostgreSQL OR tsquery string from intent search terms."""
    terms: list[str] = []
    for raw in intent.get("search_terms", []):
        # tsquery tokens: alnum only; multi-word tools become single token if joined.
        token = re.sub(r"[^a-zA-Z0-9]", "", raw.lower())
        if len(token) >= 3 and token not in _STOPWORDS:
            terms.append(token)
    terms = dedupe_keep_order(terms)[:24]
    if not terms:
        return ""
    return " | ".join(terms)


def build_fts_plaintext(intent: dict[str, Any], query: str) -> str:
    """Plaintext for plainto_tsquery / websearch — top weighted terms."""
    parts = list(intent.get("search_terms", []))[:12]
    if not parts:
        parts = extract_significant_terms(query, 10)
    return " ".join(parts)
