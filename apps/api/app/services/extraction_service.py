"""Rule-based extraction: project intent, stack inference, README parsing.

No paid LLM calls — keyword and pattern matching only.
"""
from __future__ import annotations

import re
from typing import Any

from ..utils.text import dedupe_keep_order

# ---------------------------------------------------------------------------
# Known vocabularies (lowercase keys -> canonical display names)
# ---------------------------------------------------------------------------
FRAMEWORKS: dict[str, str] = {
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "react": "React",
    "vue": "Vue",
    "svelte": "Svelte",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "express": "Express",
    "nestjs": "NestJS",
    "supabase": "Supabase",
    "firebase": "Firebase",
    "langchain": "LangChain",
    "langgraph": "LangGraph",
    "llamaindex": "LlamaIndex",
    "crewai": "CrewAI",
    "vercel ai sdk": "Vercel AI SDK",
    "tailwind": "Tailwind",
    "prisma": "Prisma",
    "drizzle": "Drizzle",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "docker": "Docker",
    "chrome extension": "Chrome Extension",
    "browser extension": "Chrome Extension",
}

TOOLS: dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "gemini": "Gemini",
    "groq": "Groq",
    "hugging face": "Hugging Face",
    "huggingface": "Hugging Face",
    "replicate": "Replicate",
    "whisper": "Whisper",
    "elevenlabs": "ElevenLabs",
    "twilio": "Twilio",
    "stripe": "Stripe",
    "clerk": "Clerk",
    "auth.js": "Auth.js",
    "pinecone": "Pinecone",
    "weaviate": "Weaviate",
    "qdrant": "Qdrant",
    "chroma": "Chroma",
    "pgvector": "pgvector",
    "mcp": "MCP",
    "claude code": "Claude Code",
    "cursor": "Cursor",
    "cline": "Cline",
    "windsurf": "Windsurf",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "ffmpeg": "ffmpeg",
    "mediapipe": "MediaPipe",
    "yt-dlp": "yt-dlp",
}

LANGUAGES: dict[str, str] = {
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "python": "Python",
    "rust": "Rust",
    "go": "Go",
    "java": "Java",
    "ruby": "Ruby",
}

APIS: dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "stripe": "Stripe",
    "github api": "GitHub",
}

MODELS: dict[str, str] = {
    "gpt-4": "GPT-4",
    "gpt-3.5": "GPT-3.5",
    "claude": "Claude",
    "whisper": "Whisper",
    "llama": "Llama",
    "gemini": "Gemini",
}

ARTIFACT_TYPES: dict[str, str] = {
    "hackathon": "hackathon_project",
    "starter": "starter_template",
    "template": "starter_template",
    "boilerplate": "starter_template",
    "mcp server": "mcp_server",
    "mcp": "mcp_server",
    "claude code": "coding_agent_workflow",
    "cursor rules": "coding_agent_workflow",
    "coding agent": "coding_agent_workflow",
    "arxiv": "research_paper",
    "research paper": "research_paper",
    "dataset": "dataset",
    "architecture": "architecture_pattern",
    "deployment": "deployment_recipe",
}

# Contextual expansions when certain phrases appear in a query.
_QUERY_EXPANSIONS: list[tuple[tuple[str, ...], dict[str, list[str]]]] = [
    (
        ("chrome extension", "browser extension"),
        {
            "frameworks": ["Chrome Extension"],
            "tools": ["Chrome Extension"],
            "tags": ["extension", "browser", "frontend"],
        },
    ),
    (
        ("rag", "retrieval augmented", "retrieval-augmented"),
        {
            "tags": ["rag", "retrieval", "vector database"],
            "tools": ["LangChain", "LlamaIndex", "pgvector"],
        },
    ),
    (
        ("video", "lecture", "summarizer", "transcription"),
        {
            "tags": ["video", "multimodal", "transcription", "summarizer"],
            "tools": ["Whisper", "ffmpeg"],
            "models": ["Whisper"],
        },
    ),
    (
        ("quiz", "flashcard"),
        {
            "tags": ["education", "quiz", "flashcards", "study"],
        },
    ),
    (
        ("mcp", "model context protocol"),
        {
            "tags": ["mcp", "coding-agent", "tools"],
            "tools": ["MCP"],
            "artifact_types": ["mcp_server", "coding_agent_workflow"],
        },
    ),
    (
        ("computer vision", "pose", "posture", "opencv", "mediapipe"),
        {
            "tags": ["computer-vision", "pose", "webcam"],
            "tools": ["MediaPipe"],
        },
    ),
    (
        ("code review", "pull request", "pr review"),
        {
            "tags": ["code-review", "pull-request", "ci"],
            "artifact_types": ["coding_agent_workflow", "open_source_project"],
        },
    ),
    (
        ("saas", "billing", "stripe"),
        {
            "tags": ["saas", "billing", "auth"],
            "tools": ["Stripe", "Supabase"],
            "frameworks": ["Next.js"],
        },
    ),
    (
        ("research paper", "research papers", "arxiv", "pdf", "paper"),
        {
            "tags": ["arxiv", "research", "pdf", "paper", "summarizer"],
            "tools": ["pgvector", "LangChain"],
        },
    ),
    (
        ("chrome extension", "browser extension"),
        {
            "frameworks": ["Chrome Extension", "React"],
            "tools": ["LangChain", "Chroma", "pgvector"],
            "tags": ["extension", "browser", "chrome", "rag"],
        },
    ),
    (
        ("vector db", "vector database", "vector store", "embeddings"),
        {
            "tags": ["vector", "embeddings", "retrieval"],
            "tools": ["pgvector", "Pinecone", "Chroma", "Qdrant"],
        },
    ),
    (
        ("summarization", "summarizer", "summarize"),
        {
            "tags": ["summarizer", "summary", "transcription"],
        },
    ),
    (
        ("architecture", "architecture ideas", "system design"),
        {
            "tags": ["architecture", "pattern", "stack"],
            "artifact_types": ["architecture_pattern", "starter_template", "open_source_project"],
        },
    ),
]


def _match_vocab(text: str, vocab: dict[str, str]) -> list[str]:
    lower = text.lower()
    found: list[str] = []
    # Longer keys first so "next.js" wins over "next".
    for key in sorted(vocab.keys(), key=len, reverse=True):
        if key in lower:
            found.append(vocab[key])
    return dedupe_keep_order(found)


def extract_project_intent(query: str) -> dict[str, Any]:
    """Infer lightweight project intent from a natural-language query."""
    lower = query.lower()

    frameworks = _match_vocab(query, FRAMEWORKS)
    tools = _match_vocab(query, TOOLS)
    languages = _match_vocab(query, LANGUAGES)
    apis = _match_vocab(query, APIS)
    models = _match_vocab(query, MODELS)
    tags: list[str] = []
    artifact_types: list[str] = []
    domains: list[str] = []

    search_terms: list[str] = []
    project_type = "general"  # refined in intent_retrieval.enrich_intent()

    for triggers, expansion in _QUERY_EXPANSIONS:
        if any(t in lower for t in triggers):
            tags.extend(expansion.get("tags", []))
            frameworks.extend(expansion.get("frameworks", []))
            tools.extend(expansion.get("tools", []))
            models.extend(expansion.get("models", []))
            artifact_types.extend(expansion.get("artifact_types", []))

    # Also infer desired artifact types from explicit mentions.
    for phrase, atype in ARTIFACT_TYPES.items():
        if phrase in lower:
            artifact_types.append(atype)

    if not artifact_types:
        artifact_types = [
            "open_source_project",
            "starter_template",
            "technical_technique",
            "coding_agent_workflow",
            "mcp_server",
        ]

    return {
        "project_type": project_type,
        "desired_artifact_types": dedupe_keep_order(artifact_types),
        "frameworks": dedupe_keep_order(frameworks),
        "languages": dedupe_keep_order(languages),
        "tools": dedupe_keep_order(tools),
        "apis": dedupe_keep_order(apis),
        "models": dedupe_keep_order(models),
        "tags": dedupe_keep_order(tags),
        "domains": dedupe_keep_order(domains),
        "search_terms": dedupe_keep_order(search_terms),
    }


def infer_artifact_type(text: str) -> str:
    lower = text.lower()
    if "hackathon" in lower:
        return "hackathon_project"
    if any(w in lower for w in ("starter", "template", "boilerplate")):
        return "starter_template"
    if "mcp server" in lower or re.search(r"\bmcp\b", lower):
        return "mcp_server"
    if any(w in lower for w in ("claude code", "cursor rules", "cline", "windsurf")):
        return "coding_agent_workflow"
    if any(w in lower for w in ("arxiv", "benchmark", "paper")):
        return "research_paper"
    if "dataset" in lower:
        return "dataset"
    if re.search(r"\bmodel\b", lower):
        return "model"
    return "open_source_project"


def extract_setup_commands(text: str) -> list[str]:
    """Pull shell commands from README code blocks."""
    commands: list[str] = []
    pattern = re.compile(r"```(?:bash|sh|shell|zsh)?\n(.*?)```", re.DOTALL | re.IGNORECASE)
    cmd_prefixes = (
        "npm ", "pnpm ", "yarn ", "pip ", "pip3 ", "python ", "docker ",
        "git ", "uvicorn ", "supabase ", "cargo ", "go ", "make ",
        "curl ", "brew ",
    )
    for block in pattern.findall(text):
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("$"):
                line = line[1:].strip()
            if line.startswith(cmd_prefixes):
                commands.append(line)
    return dedupe_keep_order(commands)[:20]


def extract_implementation_steps(text: str) -> list[str]:
    """Extract numbered or bulleted steps from README."""
    steps: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^\s*(?:\d+[\.\)]|[-*])\s+(.+)$", line)
        if m and len(m.group(1)) > 10:
            steps.append(m.group(1).strip())
    return steps[:15]


def infer_fields_from_text(
    title: str,
    description: str = "",
    readme: str = "",
) -> dict[str, Any]:
    """Infer metadata fields from title + description + README."""
    combined = f"{title}\n{description}\n{readme}"
    return {
        "artifact_type": infer_artifact_type(combined),
        "frameworks": _match_vocab(combined, FRAMEWORKS),
        "tools": _match_vocab(combined, TOOLS),
        "languages": _match_vocab(combined, LANGUAGES),
        "apis": _match_vocab(combined, APIS),
        "models": _match_vocab(combined, MODELS),
        "tags": _match_vocab(combined, {**FRAMEWORKS, **TOOLS, **LANGUAGES}),
        "setup_commands": extract_setup_commands(readme or combined),
        "implementation_steps": extract_implementation_steps(readme or combined),
    }


def build_embedding_text(artifact: dict[str, Any]) -> str:
    """Concatenate the fields we embed (not raw README).

    A structured type/stack prefix helps small bi-encoders separate MCP servers,
    papers, templates, and repos without changing the model.
    """
    lines: list[str] = []

    atype = (artifact.get("artifact_type") or "project").replace("_", " ")
    stack: list[str] = []
    for key in ("frameworks", "tools", "languages"):
        for v in artifact.get(key) or []:
            s = str(v).strip()
            if s and s not in stack:
                stack.append(s)
    prefix = f"[{atype}]"
    if stack:
        prefix += " · " + " · ".join(stack[:6])
    lines.append(prefix)

    for key in (
        "title",
        "summary",
        "what_it_helps_build",
        "technical_core",
        "practical_use_case",
        "how_to_remix",
    ):
        val = artifact.get(key)
        if val:
            lines.append(str(val))
    for key in ("implementation_steps", "setup_commands"):
        val = artifact.get(key) or []
        if val:
            lines.append(" ".join(str(x) for x in val))
    for key in ("tags", "apis", "models"):
        val = artifact.get(key) or []
        if val:
            lines.append(" ".join(str(x) for x in val))
    return "\n".join(lines).strip()
