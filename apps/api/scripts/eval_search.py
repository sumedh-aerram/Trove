#!/usr/bin/env python3
"""Retrieval eval harness using ranx (trec_eval-validated metrics).

Compares ranking configs (stage-1 hybrid only vs stage-2 with cross-encoder
reranking) on nDCG@10, MRR, Recall@10, MAP, with a paired significance test.

Relevance (qrels) is a transparent proxy: each query has expected signal terms,
and a result is graded 0..3 by how many of those terms appear in its
title/summary/tags/stack. Judgments are pooled across both configs so the
comparison is fair. This is not human gold, but it is a consistent, reproducible
yardstick for hill-climbing ranking changes.

Run (from apps/api):
  DATABASE_URL=postgresql://postgres:postgres@localhost:5433/build_radar \
    PYTHONPATH=. python scripts/eval_search.py
"""
from __future__ import annotations

import asyncio
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
    ("Next.js Supabase starter template", ["next", "supabase", "starter", "template", "boilerplate", "auth"]),
    ("agent framework with tool use", ["agent", "framework", "tool", "langchain", "workflow", "function"]),
    ("PDF document question answering", ["pdf", "document", "qa", "question", "rag", "chat"]),
    ("image generation diffusion app", ["image", "diffusion", "generation", "stable", "art", "text-to-image"]),
]

K = 10
LIMIT = 20


def grade(artifact: dict, terms: list[str]) -> int:
    """Graded relevance 0..3 = how many expected terms appear in the artifact."""
    blob = " ".join(
        str(artifact.get(f) or "")
        for f in ("title", "summary", "what_it_helps_build", "technical_core")
    ).lower()
    blob += " " + " ".join(
        x.lower() for key in ("tags", "tools", "frameworks") for x in (artifact.get(key) or [])
    )
    return min(3, sum(1 for t in terms if t in blob))


async def run() -> None:
    from ranx import Qrels, Run, compare

    await init_pool()
    configs = {"stage-1 hybrid": False, "stage-2 +rerank": True}
    qrels_dict: dict[str, dict[str, int]] = {}
    runs: dict[str, dict[str, dict[str, float]]] = {name: {} for name in configs}

    try:
        for qi, (q, terms) in enumerate(EVALSET):
            qid = f"q{qi}"
            pooled: dict[str, dict] = {}
            for name, rerank in configs.items():
                res = await hybrid_search(q, limit=LIMIT, rerank=rerank)
                scores: dict[str, float] = {}
                for rank, r in enumerate(res["results"]):
                    did = str(r["id"])
                    scores[did] = float(r.get("final_score") or 0) + (LIMIT - rank) * 1e-6
                    pooled[did] = r
                runs[name][qid] = scores
            # graded judgments pooled across both configs
            judged = {did: grade(art, terms) for did, art in pooled.items()}
            if any(v > 0 for v in judged.values()):
                qrels_dict[qid] = judged
            else:
                # keep the query but mark nothing relevant (rare)
                qrels_dict[qid] = {did: 0 for did in judged}

        qrels = Qrels(qrels_dict)
        run_objs = [Run(runs[name], name=name) for name in configs]
        report = compare(
            qrels=qrels,
            runs=run_objs,
            metrics=["ndcg@10", "mrr", "recall@10", "map@10"],
            max_p=0.05,  # paired Student's t-test threshold
        )
        print("\n=== Trove retrieval eval (ranx, " + str(len(EVALSET)) + " queries) ===\n")
        print(report)
        print(
            "\nSuperscript letters mark configs a result is significantly better than (paired t-test, p<0.05)."
        )
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(run())
