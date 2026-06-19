"""Central, broad discovery vocabulary for all crawlers.

Kept wide on purpose: crawlers rotate through windows of these (see cursor.py),
so over many runs the index keeps growing across the whole builder surface
instead of re-hitting the same handful of queries.
"""
from __future__ import annotations

# Hacker News search terms (Algolia).
HN_TERMS: list[str] = [
    "AI hackathon project", "Next.js AI app", "RAG app", "LangChain", "LlamaIndex",
    "MCP server", "Model Context Protocol", "Claude Code", "Cursor IDE", "AI agent",
    "open source AI app", "computer vision app", "Whisper transcription", "Chrome extension AI",
    "vector database", "pgvector", "local LLM", "llama.cpp", "ollama", "fine-tuning LLM",
    "AI coding assistant", "code review AI", "agent framework", "multi-agent", "voice AI agent",
    "text to speech", "speech to text", "diffusion model", "image generation app",
    "AI SaaS starter", "Supabase", "Stripe billing", "auth boilerplate", "realtime app",
    "websocket app", "edge functions", "serverless", "self-hosted", "open source alternative",
    "developer tool", "CLI tool", "terminal app", "TUI", "API gateway", "embeddings search",
    "semantic search", "knowledge base", "PDF chat", "document QA", "web scraper",
    "browser automation", "playwright", "data pipeline", "ETL", "workflow automation",
    "no-code", "low-code", "prompt engineering", "evals", "LLM evaluation", "guardrails",
    "function calling", "tool use", "structured output", "JSON mode", "streaming UI",
]

# arXiv free-text topics (combined with categories at query time).
ARXIV_TOPICS: list[str] = [
    "large language model agents", "retrieval augmented generation", "code generation",
    "repository-level code generation", "automated program repair", "LLM tool use",
    "multimodal agents", "vision language models", "speech recognition", "text to speech",
    "efficient LLM inference", "model quantization", "LLM evaluation benchmark",
    "instruction tuning", "reasoning large language models", "chain of thought",
    "retrieval dense passage", "vector search approximate nearest neighbor",
    "diffusion models image generation", "video understanding", "document understanding",
    "knowledge graphs LLM", "agent planning", "reinforcement learning from human feedback",
    "long context transformers", "mixture of experts", "prompt optimization",
    "code search semantic", "software engineering agents", "test generation",
]

# arXiv categories to bias toward builder-relevant CS work.
ARXIV_CATEGORIES: list[str] = ["cs.SE", "cs.CL", "cs.AI", "cs.LG", "cs.CV", "cs.IR"]

# GitHub discovery queries (quoted at build time).
GITHUB_QUERIES: list[str] = [
    "AI hackathon project", "Next.js AI app", "full stack AI app", "RAG Next.js Supabase",
    "LangChain Next.js", "LlamaIndex app", "AI agent project", "multimodal AI app",
    "voice agent project", "video summarizer", "lecture summarizer", "research paper summarizer",
    "Chrome extension AI", "AI flashcard app", "computer vision hackathon", "Whisper transcription app",
    "AI resume builder", "AI code review", "MCP server", "Claude Code skill", "Cursor rules",
    "vector search app", "pgvector starter", "ollama app", "local LLM app", "RAG chatbot",
    "PDF chat app", "document QA", "semantic search engine", "AI SaaS starter", "Supabase starter",
    "Stripe SaaS boilerplate", "realtime chat app", "agent framework", "multi-agent system",
    "text to speech app", "image generation app", "AI notetaker", "meeting transcription",
    "browser automation agent",
]
