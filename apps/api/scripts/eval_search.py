#!/usr/bin/env python3
"""Retrieval eval harness: recall@k, MRR, nDCG@10, rerank ON vs OFF.

Relevance is a transparent proxy: a result is graded by how many of a query's
expected signal terms appear in its title/summary/tags/stack (0..3+). That's not
human-labeled gold, but it's a consistent, reproducible yardstick for comparing
ranking configs — which is exactly what we need to show that stage-2
cross-encoder reranking improves ordering over first-stage hybrid retrieval.

Run (from apps/api):
  DATABASE_URL=postgresql://postgres:postgres@localhost:5433/build_radar \
    PYTHONPATH=. python scripts/eval_search.py
"""
from __future__ import annotations

import asyncio
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import close_pool, init_pool  # noqa: E402
from app.services.search_service import hybrid_search  # noqa: E402

# query -> expected signal terms a relevant result should contain.
EVALSET: list[tuple[str, list[str]]] = [
    ("RAG chrome extension for research papers", ["rag", "extension", "chrome", "paper", "retrieval", "pdf"]),
    ("AI lecture summarizer with quiz generation", ["lecture", "summar", "quiz", "transcri", "whisper", "video"]),
    ("MCP server for coding agents", ["mcp", "agent", "tool", "server", "cursor", "claude"]),
    ("realtime computer vision posture detection", ["vision", "pose", "posture", "webcam", "mediapipe", "opencv"]),
    ("full stack AI SaaS with auth and billing", ["saas", "auth", "billing", "stripe", "supabase", "next"]),
    ("voice agent low latency speech", ["voice", "speech", "tts", "stt", "realtime", "audio"]),
    ("local LLM inference with quantization", ["local", "llm", "quantiz", "inference", "ollama", "llama"]),
    ("vector search semantic retrieval", ["vector", "embedding", "semantic", "retrieval", "search", "pgvector"]),
]

K = 10


def grade(artifact: dict, terms: list[str]) -> int:
    """Graded relevance: count distinct expected terms present in the artifact text."""
    blob = " ".join(
        str(artifact.get(f) or "")
        for f in ("title", "summary", "what_it_helps_build", "technical_core")
    ).lower()
    blob += " " + " ".join(
        x.lower() for key in ("tags", "tools", "frameworks") for x in (artifact.get(key) or [])
    )
    return sum(1 for t in terms if t in blob)


def dcg(gains: list[float]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(rels: list[int], k: int) -> float:
    gains = [float(r) for r in rels[:k]]
    ideal = sorted([float(r) for r in rels], reverse=True)[:k]
    idcg = dcg(ideal)
    return dcg(gains) / idcg if idcg > 0 else 0.0


def metrics_for(results: list[dict], terms: list[str], k: int) -> tuple[float, float, float]:
    rels = [grade(r, terms) for r in results[:k]]
    binary = [1 if r >= 2 else 0 for r in rels]  # "relevant" = >=2 expected terms
    recall = sum(binary) / max(1, min(k, len([1 for _ in results[:k]])))  # frac of top-k that are relevant
    mrr = 0.0
    for i, b in enumerate(binary):
        if b:
            mrr = 1.0 / (i + 1)
            break
    return recall, mrr, ndcg_at_k(rels, k)


async def run() -> None:
    await init_pool()
    try:
        for label, use_rerank in (("STAGE-1 (hybrid only)", False), ("STAGE-2 (+ rerank)", True)):
            tot_recall = tot_mrr = tot_ndcg = 0.0
            for q, terms in EVALSET:
                res = await hybrid_search(q, limit=K, rerank=use_rerank)
                recall, mrr, ndcg = metrics_for(res["results"], terms, K)
                tot_recall += recall
                tot_mrr += mrr
                tot_ndcg += ndcg
            n = len(EVALSET)
            print(
                f"{label:24}  recall@{K}={tot_recall / n:.3f}  "
                f"MRR={tot_mrr / n:.3f}  nDCG@{K}={tot_ndcg / n:.3f}"
            )
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(run())
