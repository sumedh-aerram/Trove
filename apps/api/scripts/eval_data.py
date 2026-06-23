"""Eval data assembly for the self-improving loop.

Separates two roles cleanly:
  - CURATED (scripts/eval_search.EVALSET): hand-written, FROZEN. The held-out
    anchor we validate against. The loop never trains away its honesty.
  - HARVESTED (eval/harvested_queries.json): auto-grown from real usage. Used to
    widen training coverage.
  - FEEDBACK (eval/feedback_pairs.json): real click/star positives, mapped to
    qrels overlays keyed by the COMBINED evalset index, with a graded weight.

`combined_evalset()` = curated + harvested (training view).
`feedback_overlay()` = qid -> {artifact_id: grade} aligned to combined indices.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.eval_search import EVALSET

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
GRADE_CLICK = 2
GRADE_STAR = 3


def load_harvested_queries() -> list[tuple[str, list[str]]]:
    path = EVAL_DIR / "harvested_queries.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [(d["query"], d["terms"]) for d in data if d.get("terms")]


def load_feedback_pairs() -> list[dict]:
    path = EVAL_DIR / "feedback_pairs.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def merge_training_pairs(feedback: list[dict], curated: list[dict]) -> list[dict]:
    """Dedupe by (query, positive_id); feedback wins over curated on conflict."""
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for p in feedback + curated:
        q = str(p.get("query", "")).strip()
        pid = str(p.get("positive_id", ""))
        if not q or not pid:
            continue
        key = (q.lower(), pid)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


async def load_curated_training_pairs() -> list[dict]:
    """One top oracle-matched artifact per frozen curated eval query."""
    from scripts.eval_search import EVALSET, build_oracle_qrels

    qrels, _ = await build_oracle_qrels(EVALSET)
    pairs: list[dict] = []
    for qi, (query, _) in enumerate(EVALSET):
        judged = qrels.get(f"q{qi}", {})
        if not judged:
            continue
        top_id, grade = max(judged.items(), key=lambda kv: kv[1])
        pairs.append(
            {
                "query": query,
                "positive_id": top_id,
                "kind": "curated",
                "weight": float(grade),
            }
        )
    return pairs


def combined_evalset(include_harvested: bool = True) -> list[tuple[str, list[str]]]:
    """Curated (frozen) first, then harvested. Curated indices stay stable."""
    out = list(EVALSET)
    if include_harvested:
        seen = {q.lower() for q, _ in out}
        for q, terms in load_harvested_queries():
            if q.lower() not in seen:
                out.append((q, terms))
                seen.add(q.lower())
    return out


def feedback_overlay(evalset: list[tuple[str, list[str]]]) -> dict[str, dict[str, int]]:
    """Map click/star pairs to qrels overlays keyed by qid of `evalset`."""
    idx_by_query = {q.lower(): i for i, (q, _t) in enumerate(evalset)}
    overlay: dict[str, dict[str, int]] = {}
    for p in load_feedback_pairs():
        i = idx_by_query.get(str(p.get("query", "")).lower())
        if i is None:
            continue
        qid = f"q{i}"
        grade = GRADE_STAR if p.get("kind") == "star" else GRADE_CLICK
        overlay.setdefault(qid, {})
        aid = p["positive_id"]
        overlay[qid][aid] = max(overlay[qid].get(aid, 0), grade)
    return overlay
