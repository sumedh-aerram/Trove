#!/usr/bin/env python3
"""Retrieval eval harness using ranx (trec_eval-validated metrics).

Compares ranking configs (stage-1 hybrid vs stage-2 with cross-encoder rerank)
on nDCG@10, MRR, Recall@10, MAP, with a paired significance test and bootstrap
confidence intervals.

Relevance (qrels) is a transparent, ranker-INDEPENDENT proxy. For each query we
score *every* artifact in the corpus by how many expected signal terms it
contains, and call it relevant when at least MIN_MATCHES distinct terms appear.
Because the relevant set is built over the whole corpus (not just what the
searcher returned), Recall@k can finally see documents the retriever missed.
This is not human gold, but it is a consistent, reproducible yardstick.

Run (from apps/api):
  DATABASE_URL=postgresql://postgres:postgres@localhost:5433/build_radar \
    PYTHONPATH=. python scripts/eval_search.py
"""
from __future__ import annotations

import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db  # noqa: E402
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
    # --- expanded set for tighter confidence intervals ---
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
    # --- batch 3: keep growing the suite over time for tighter CIs + a better LTR model ---
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

K = 10
LIMIT = 20
MIN_MATCHES = 2          # >= this many expected terms => relevant
MAX_RELEVANT = 80        # cap relevant set per query (avoid pathological breadth)
BOOTSTRAP_ITERS = 2000


def _blob(row: dict) -> str:
    """Same text surface used for query relevance grading."""
    text = " ".join(
        str(row.get(f) or "")
        for f in ("title", "summary", "what_it_helps_build", "technical_core")
    ).lower()
    arrays = " ".join(
        x.lower()
        for key in ("tags", "tools", "frameworks", "languages")
        for x in (row.get(key) or [])
    )
    return text + " " + arrays


def grade(blob: str, terms: list[str]) -> int:
    """Graded relevance = how many distinct expected terms appear (0..len)."""
    return sum(1 for t in terms if t in blob)


async def build_oracle_qrels(
    evalset: list[tuple[str, list[str]]] | None = None,
    feedback: dict[str, dict[str, int]] | None = None,
) -> tuple[dict[str, dict[str, int]], dict[str, set[str]]]:
    """Ranker-independent relevant sets, graded over the WHOLE corpus.

    `evalset` defaults to the curated EVALSET. `feedback` optionally overlays
    real click/star labels per query index (qid -> {artifact_id: grade}); those
    observed positives are merged in at max grade, so the loop learns from actual
    user choices, not only the term heuristic.

    Returns (qrels, relevant_ids_by_query).
    """
    evalset = evalset if evalset is not None else EVALSET
    rows = await db.fetch(
        "SELECT id, title, summary, what_it_helps_build, technical_core, "
        "tags, tools, frameworks, languages FROM artifacts"
    )
    corpus = [(str(r["id"]), _blob(dict(r))) for r in rows]

    qrels: dict[str, dict[str, int]] = {}
    relevant_ids: dict[str, set[str]] = {}
    for qi, (_q, terms) in enumerate(evalset):
        qid = f"q{qi}"
        graded = [(did, grade(blob, terms)) for did, blob in corpus]
        graded = [(did, g) for did, g in graded if g >= MIN_MATCHES]
        graded.sort(key=lambda x: x[1], reverse=True)
        graded = graded[:MAX_RELEVANT]
        judged = {did: g for did, g in graded}
        if feedback and qid in feedback:
            for did, g in feedback[qid].items():
                judged[did] = max(judged.get(did, 0), g)
        qrels[qid] = judged
        relevant_ids[qid] = set(judged)
    return qrels, relevant_ids


def bootstrap_ci(per_query: list[float], iters: int = BOOTSTRAP_ITERS) -> tuple[float, float, float]:
    """Mean + 95% percentile bootstrap CI by resampling queries with replacement."""
    n = len(per_query)
    if n == 0:
        return 0.0, 0.0, 0.0
    rng = random.Random(13)
    means = []
    for _ in range(iters):
        sample = [per_query[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * iters)]
    hi = means[int(0.975 * iters)]
    mean = sum(per_query) / n
    return mean, lo, hi


async def run() -> None:
    from ranx import Qrels, Run, compare, evaluate

    await init_pool()
    configs = {"stage-1 hybrid": False, "stage-2 +rerank": True}
    runs: dict[str, dict[str, dict[str, float]]] = {name: {} for name in configs}

    # diagnostics
    pool_recall: dict[str, list[float]] = {name: [] for name in configs}   # relevant found anywhere in returned list
    top_recall: dict[str, list[float]] = {name: [] for name in configs}    # relevant in top-K

    try:
        qrels_dict, relevant_ids = await build_oracle_qrels()

        for qi, (q, _terms) in enumerate(EVALSET):
            qid = f"q{qi}"
            rel = relevant_ids[qid]
            for name, rerank in configs.items():
                res = await hybrid_search(q, limit=LIMIT, rerank=rerank)
                results = res["results"]
                scores: dict[str, float] = {}
                returned_ids: list[str] = []
                for rank, r in enumerate(results):
                    did = str(r["id"])
                    returned_ids.append(did)
                    scores[did] = float(r.get("final_score") or 0) + (LIMIT - rank) * 1e-6
                runs[name][qid] = scores
                if rel:
                    found = sum(1 for d in returned_ids if d in rel)
                    in_top = sum(1 for d in returned_ids[:K] if d in rel)
                    denom = min(len(rel), LIMIT)
                    pool_recall[name].append(found / denom)
                    top_recall[name].append(in_top / min(len(rel), K))

        qrels = Qrels(qrels_dict)
        run_objs = [Run(runs[name], name=name) for name in configs]

        print(f"\n=== Trove retrieval eval (ranx, {len(EVALSET)} queries, oracle qrels) ===\n")
        report = compare(
            qrels=qrels,
            runs=run_objs,
            metrics=["ndcg@10", "mrr", "recall@10", "map@10"],
            max_p=0.05,
        )
        print(report)
        print(
            "\nSuperscript letters mark configs a result is significantly better than "
            "(paired t-test, p<0.05)."
        )

        # bootstrap CI on nDCG@10 per config
        print("\n--- nDCG@10 with 95% bootstrap CI (resampling queries) ---")
        for name in configs:
            per_q = list(evaluate(qrels, run_objs[list(configs).index(name)], "ndcg@10", return_mean=False))
            mean, lo, hi = bootstrap_ci(per_q)
            print(f"  {name:18s} {mean:.3f}  [{lo:.3f}, {hi:.3f}]")

        # diagnostics: separate retrieval misses from ranking misses
        print("\n--- diagnostics: where do relevant docs go? ---")
        print(f"  {'config':18s} {'pool_recall@20':>14s} {'top_recall@10':>14s}")
        for name in configs:
            pr = sum(pool_recall[name]) / len(pool_recall[name]) if pool_recall[name] else 0.0
            tr = sum(top_recall[name]) / len(top_recall[name]) if top_recall[name] else 0.0
            print(f"  {name:18s} {pr:>14.3f} {tr:>14.3f}")
        print(
            "\n  pool_recall@20 = fraction of relevant docs the retriever surfaced at all.\n"
            "  top_recall@10  = fraction of relevant docs that reached the top 10.\n"
            "  Low pool_recall => retrieval problem (fix stage-1). High pool but low\n"
            "  top => ranking problem (fix fusion/scoring/rerank)."
        )

        from app.config import get_settings

        if get_settings().ltr_enabled:
            print(
                "\n  !!! LTR IS ENABLED: the learned reranker was TRAINED on these exact\n"
                "  queries, so the numbers above are IN-SAMPLE (optimistically biased by\n"
                "  memorization). The HONEST LTR gain is the nested-CV held-out result\n"
                "  from scripts/train_ltr.py (nDCG@10 0.605 -> 0.629). For a clean,\n"
                "  leakage-free retrieval benchmark run with LTR_ENABLED=false."
            )
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(run())
