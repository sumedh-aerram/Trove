#!/usr/bin/env python3
"""Harvest real usage into (1) grown eval queries and (2) training pairs.

Reads search_events and writes two artifacts under apps/api/eval/:
  - harvested_queries.json : [{"query", "terms"}]   (coverage; auto-labeled with
    the same significant-term heuristic the curated oracle uses)
  - feedback_pairs.json    : [{"query", "positive_id", "weight", "kind"}]
    built from clicks/stars, with POSITION-BIAS correction.

Position-bias correction (IPS): a click at rank 1 is partly just "it was on
top". We estimate examination propensity per position from impressions
(CTR(pos) / CTR(top)) and weight each click by 1/propensity, clipped. Stars are
treated as stronger positives than clicks. The curated EVALSET stays frozen and
is never written here, so it remains a clean held-out anchor.

Run (from apps/api):
  DATABASE_URL=... PYTHONPATH=. python scripts/harvest_eval.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import close_pool, fetch, init_pool  # noqa: E402
from app.services.extraction_service import extract_project_intent  # noqa: E402
from app.services.intent_retrieval import enrich_intent, extract_significant_terms  # noqa: E402
from scripts.eval_search import EVALSET  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
MIN_QUERY_COUNT = 1          # keep queries seen at least this many times
MAX_TERMS = 6
IPS_CLIP = 5.0               # cap inverse-propensity weights to control variance
STAR_BOOST = 2.0             # a save is a stronger signal than a click


def derive_terms(query: str) -> list[str]:
    """Auto-label a harvested query the same way the oracle grades: salient terms
    plus any tools/frameworks the intent extractor recognizes."""
    intent = enrich_intent(query, extract_project_intent(query))
    terms = extract_significant_terms(query, MAX_TERMS * 2)
    for key in ("tools", "frameworks", "tags"):
        for x in (intent.get(key) or []):
            terms.append(str(x).lower())
    seen, out = set(), []
    for t in terms:
        t = t.lower().strip()
        if t and t not in seen and len(t) >= 3:
            seen.add(t)
            out.append(t)
    return out[:MAX_TERMS]


def position_propensities(impressions: list[list[dict]], clicks_by_pos: dict[int, int]) -> dict[int, float]:
    """Estimate examination propensity per position: CTR(pos) normalized to top."""
    shown_by_pos: dict[int, int] = defaultdict(int)
    for imp in impressions:
        for item in imp:
            shown_by_pos[int(item.get("pos", 0))] += 1
    ctr: dict[int, float] = {}
    for pos, shown in shown_by_pos.items():
        ctr[pos] = (clicks_by_pos.get(pos, 0) / shown) if shown else 0.0
    base = ctr.get(0, 0.0) or max(ctr.values(), default=0.0) or 1.0
    return {pos: (c / base if c > 0 else 1.0) for pos, c in ctr.items()}


async def main() -> None:
    await init_pool()
    try:
        rows = await fetch(
            "SELECT event_type, query, impression, clicked_artifact_id, "
            "saved_artifact_id, position FROM search_events"
        )
        searches = [r for r in rows if r["event_type"] == "search"]
        clicks = [r for r in rows if r["event_type"] == "click"]
        stars = [r for r in rows if r["event_type"] == "star"]

        # --- 1) grown eval queries (coverage) ---
        curated = {q.lower() for q, _ in EVALSET}
        counts: dict[str, int] = defaultdict(int)
        for r in searches:
            counts[r["query"].strip()] += 1
        harvested = []
        for query, n in sorted(counts.items(), key=lambda x: -x[1]):
            if n < MIN_QUERY_COUNT or query.lower() in curated:
                continue
            terms = derive_terms(query)
            if len(terms) >= 2:
                harvested.append({"query": query, "terms": terms, "seen": n})

        # --- 2) position-bias-corrected feedback pairs ---
        impressions = [json.loads(r["impression"]) if isinstance(r["impression"], str)
                       else (r["impression"] or []) for r in searches]
        clicks_by_pos: dict[int, int] = defaultdict(int)
        for r in clicks + stars:
            if r["position"] is not None:
                clicks_by_pos[int(r["position"])] += 1
        prop = position_propensities(impressions, clicks_by_pos)

        pairs = []
        for r, kind in [(c, "click") for c in clicks] + [(s, "star") for s in stars]:
            aid = r["clicked_artifact_id"] or r["saved_artifact_id"]
            if not aid:
                continue
            pos = int(r["position"]) if r["position"] is not None else 0
            w = min(IPS_CLIP, 1.0 / max(prop.get(pos, 1.0), 1e-3))
            if kind == "star":
                w *= STAR_BOOST
            pairs.append({"query": r["query"], "positive_id": str(aid),
                          "weight": round(w, 3), "kind": kind})

        EVAL_DIR.mkdir(exist_ok=True)
        (EVAL_DIR / "harvested_queries.json").write_text(json.dumps(harvested, indent=2))
        (EVAL_DIR / "feedback_pairs.json").write_text(json.dumps(pairs, indent=2))

        print(f"events: {len(searches)} searches, {len(clicks)} clicks, {len(stars)} stars")
        print(f"harvested {len(harvested)} new eval queries -> eval/harvested_queries.json")
        print(f"built {len(pairs)} feedback pairs -> eval/feedback_pairs.json")
        if not searches:
            print("\n(No usage logged yet. Run some searches/clicks, then re-run this.)")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
