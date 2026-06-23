"""Frozen curated eval queries with category tags and gold-subset hints.

EVALSET stays a list of (query, terms) tuples for backward compatibility.
Gold hints are title substrings: a gold query passes if any hinted artifact
appears in the top-K results (stricter, human-aligned check).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalQuery:
    query: str
    terms: list[str]
    category: str = "general"
    synonyms: tuple[str, ...] = ()
    gold_hints: tuple[str, ...] = ()  # title substring hints for gold-subset pass


# Global synonym expansions applied during oracle grading.
TERM_SYNONYMS: dict[str, tuple[str, ...]] = {
    "llm": ("language model", "large language"),
    "mcp": ("model context protocol",),
    "rag": ("retrieval augmented", "retrieval-augmented"),
    "k8s": ("kubernetes",),
    "stt": ("speech to text", "speech-to-text"),
    "tts": ("text to speech", "text-to-speech"),
    "ci": ("continuous integration",),
    "cd": ("continuous deployment", "continuous delivery"),
    "vlm": ("vision language", "vision-language"),
    "gnn": ("graph neural",),
    "ssg": ("static site",),
}


_RAW: list[tuple[str, list[str]]] = [
    ("RAG chrome extension for research papers", ["rag", "extension", "chrome", "paper", "retrieval", "pdf"]),
    ("AI lecture summarizer with quiz generation", ["lecture", "summar", "quiz", "transcri", "whisper", "video"]),
    ("MCP server for coding agents", ["mcp", "agent", "tool", "server", "cursor", "claude"]),
    ("realtime computer vision posture detection", ["vision", "pose", "posture", "webcam", "mediapipe", "opencv"]),
    ("full stack AI SaaS with auth and billing", ["saas", "auth", "billing", "stripe", "supabase", "next"]),
    ("voice agent low latency speech", ["voice", "speech", "tts", "stt", "realtime", "audio"]),
    ("local LLM inference with quantization", ["local", "llm", "quantiz", "inference", "ollama", "llama"]),
    ("vector search semantic retrieval", ["vector", "embedding", "semantic", "retrieval", "search", "pgvector"]),
    ("Next.js Supabase starter template", ["next", "supabase", "starter", "template", "boilerplate", "auth"]),
    ("agent framework with tool use", ["agent", "framework", "tool", "langchain", "workflow", "function"]),
    ("PDF document question answering", ["pdf", "document", "qa", "question", "rag", "chat"]),
    ("image generation diffusion app", ["image", "diffusion", "generation", "stable", "art", "text-to-image"]),
    ("fine-tune LLM with LoRA on custom data", ["fine-tun", "lora", "llm", "train", "peft", "dataset"]),
    ("text to speech voice cloning", ["tts", "voice", "clone", "speech", "audio", "synthesis"]),
    ("web scraper with playwright automation", ["scrap", "playwright", "crawl", "browser", "automation", "selenium"]),
    ("kubernetes deployment with helm charts", ["kubernetes", "k8s", "helm", "deploy", "container", "docker"]),
    ("realtime chat app with websockets", ["chat", "websocket", "realtime", "message", "socket", "live"]),
    ("recommendation system collaborative filtering", ["recommend", "collaborative", "filter", "rank", "embedding", "user"]),
    ("speech to text transcription whisper", ["whisper", "transcri", "speech", "stt", "audio", "subtitle"]),
    ("stable diffusion image editing inpainting", ["diffusion", "inpaint", "image", "edit", "mask", "stable"]),
    ("data pipeline orchestration airflow", ["pipeline", "airflow", "etl", "orchestr", "workflow", "dag"]),
    ("github actions ci cd automation", ["github", "action", "ci", "cd", "pipeline", "deploy"]),
    ("react native mobile app with expo", ["react", "native", "mobile", "expo", "ios", "android"]),
    ("knowledge graph from documents", ["knowledge", "graph", "entity", "document", "extract", "neo4j"]),
    ("time series forecasting deep learning", ["time", "series", "forecast", "lstm", "predict", "temporal"]),
    ("prompt engineering evaluation framework", ["prompt", "eval", "llm", "test", "benchmark", "framework"]),
    ("multimodal vision language model", ["multimodal", "vision", "language", "clip", "image", "vlm"]),
    ("serverless api with edge functions", ["serverless", "edge", "api", "function", "lambda", "deploy"]),
    ("graph neural network molecule prediction", ["graph", "neural", "gnn", "molecule", "node", "predict"]),
    ("autonomous agent web browsing", ["agent", "autonomous", "browse", "web", "tool", "task"]),
    ("open source alternative to notion", ["notion", "note", "markdown", "self-host", "app", "open"]),
    ("browser automation end to end testing", ["browser", "test", "playwright", "selenium", "automation", "e2e"]),
    ("llm observability tracing and evals", ["llm", "observability", "trace", "monitor", "eval", "langsmith"]),
    ("natural language to sql query interface", ["sql", "query", "natural", "language", "database", "text-to-sql"]),
    ("realtime collaborative editor with crdt", ["collaborative", "crdt", "editor", "realtime", "sync", "yjs"]),
    ("embeddings database for similarity search", ["embedding", "vector", "database", "similarity", "faiss", "index"]),
    ("discord bot with ai chat integration", ["discord", "bot", "chat", "message", "integration", "ai"]),
    ("personal finance tracking dashboard", ["finance", "budget", "expense", "dashboard", "track", "money"]),
    ("static site generator for markdown blog", ["static", "site", "generator", "markdown", "blog", "ssg"]),
    ("rust async web server framework", ["rust", "web", "server", "async", "tokio", "axum"]),
    ("computer use agent controlling the screen", ["computer", "agent", "screen", "control", "automation", "gui"]),
    ("pdf invoice data extraction pipeline", ["pdf", "invoice", "extract", "ocr", "parse", "document"]),
    ("ai music generation from text", ["music", "audio", "generation", "midi", "sound", "ai"]),
    ("automated code review github bot", ["code", "review", "github", "bot", "pr", "automation"]),
    ("self hosted password manager", ["password", "manager", "self-host", "vault", "secret", "encryption"]),
    ("video editing automation with ffmpeg", ["video", "edit", "ffmpeg", "clip", "render", "automation"]),
    ("llm cost optimization and caching", ["llm", "cost", "cache", "optimize", "token", "budget"]),
    ("graphql api gateway with federation", ["graphql", "api", "gateway", "schema", "resolver", "federation"]),
    ("anomaly detection for metrics monitoring", ["anomaly", "detect", "metric", "monitor", "outlier", "alert"]),
    ("fine tune embeddings for retrieval", ["embedding", "fine-tun", "retrieval", "contrastive", "train", "sentence"]),
]

_CATEGORIES = [
    "rag", "education", "agents", "vision", "saas", "voice", "llm", "search",
    "templates", "agents", "rag", "generative", "llm", "voice", "automation",
    "infra", "realtime", "ml", "speech", "generative", "data", "devops",
    "mobile", "knowledge", "ml", "llm", "multimodal", "serverless", "ml",
    "agents", "productivity", "automation", "observability", "data", "realtime",
    "search", "bots", "finance", "web", "systems", "agents", "documents",
    "generative", "devops", "security", "media", "llm", "api", "monitoring",
    "search",
]

# Title-hint gold subset: passes if any top-K result title matches a hint.
_GOLD_HINTS: dict[int, tuple[str, ...]] = {
    0: ("rag", "chrome", "extension"),
    2: ("mcp",),
    7: ("vector", "pgvector", "embedding"),
    8: ("supabase", "next"),
    9: ("agent", "langchain"),
    10: ("pdf", "rag"),
    35: ("vector", "embedding", "faiss", "similarity"),
    39: ("computer", "agent", "gui", "screen"),
    6: ("ollama", "llama", "local"),
    41: ("password", "vault", "bitwarden"),
    32: ("sql", "text-to-sql", "database"),
    30: ("notion", "note", "markdown"),
}


def _build_queries() -> list[EvalQuery]:
    out: list[EvalQuery] = []
    for i, (q, terms) in enumerate(_RAW):
        out.append(
            EvalQuery(
                query=q,
                terms=terms,
                category=_CATEGORIES[i] if i < len(_CATEGORIES) else "general",
                gold_hints=_GOLD_HINTS.get(i, ()),
            )
        )
    return out


EVAL_QUERIES: list[EvalQuery] = _build_queries()
EVALSET: list[tuple[str, list[str]]] = [(q.query, q.terms) for q in EVAL_QUERIES]
GOLD_QUERY_INDICES: tuple[int, ...] = tuple(sorted(_GOLD_HINTS.keys()))

# Shared eval harness constants
MIN_MATCHES = 2          # legacy alias; oracle uses MIN_GRADE_POINTS in eval_oracle
MAX_RELEVANT = 80
