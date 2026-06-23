"""Oracle qrels: ranker-independent relevance grading over the full corpus."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app import db
from scripts.eval_queries import EVALSET, MAX_RELEVANT, TERM_SYNONYMS

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
TITLE_WEIGHT = 2
BODY_WEIGHT = 1
MIN_GRADE_POINTS = 3
SNAPSHOT_PATH = EVAL_DIR / "qrels_snapshot.json"


def expand_terms(terms: list[str], extra: tuple[str, ...] = ()) -> list[str]:
    """Expand eval terms with global synonyms (deduped, lowercase)."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in list(terms) + list(extra):
        t = raw.lower().strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
        for syn in TERM_SYNONYMS.get(t, ()):
            s = syn.lower()
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def _body_blob(row: dict) -> str:
    text = " ".join(
        str(row.get(f) or "")
        for f in ("summary", "what_it_helps_build", "technical_core")
    ).lower()
    arrays = " ".join(
        x.lower()
        for key in ("tags", "tools", "frameworks", "languages")
        for x in (row.get(key) or [])
    )
    return text + " " + arrays


def grade_row(row: dict, terms: list[str], extra_synonyms: tuple[str, ...] = ()) -> int:
    """Weighted term hits: title matches count double."""
    title = (row.get("title") or "").lower()
    body = _body_blob(row)
    expanded = expand_terms(terms, extra_synonyms)
    points = 0
    for t in expanded:
        if t in title:
            points += TITLE_WEIGHT
        elif t in body:
            points += BODY_WEIGHT
    return points


def grade_blob_legacy(blob: str, terms: list[str]) -> int:
    """Legacy flat blob grading (used in tests / compatibility)."""
    return sum(1 for t in terms if t in blob)


async def build_oracle_qrels(
    evalset: list[tuple[str, list[str]]] | None = None,
    feedback: dict[str, dict[str, int]] | None = None,
    *,
    write_snapshot: bool = False,
) -> tuple[dict[str, dict[str, int]], dict[str, set[str]]]:
    """Ranker-independent relevant sets, graded over the WHOLE corpus."""
    evalset = evalset if evalset is not None else EVALSET
    query_meta = {q.query: q for q in EVAL_QUERIES}

    rows = await db.fetch(
        "SELECT id, title, summary, what_it_helps_build, technical_core, "
        "tags, tools, frameworks, languages FROM artifacts"
    )
    corpus_rows = [dict(r) for r in rows]

    qrels: dict[str, dict[str, int]] = {}
    relevant_ids: dict[str, set[str]] = {}
    for qi, (query, terms) in enumerate(evalset):
        qid = f"q{qi}"
        meta = query_meta.get(query)
        extra = meta.synonyms if meta else ()
        graded = [
            (str(row["id"]), grade_row(row, terms, extra))
            for row in corpus_rows
        ]
        graded = [(did, g) for did, g in graded if g >= MIN_GRADE_POINTS]
        graded.sort(key=lambda x: x[1], reverse=True)
        graded = graded[:MAX_RELEVANT]
        judged = {did: g for did, g in graded}
        if feedback and qid in feedback:
            for did, g in feedback[qid].items():
                judged[did] = max(judged.get(did, 0), g)
        qrels[qid] = judged
        relevant_ids[qid] = set(judged)

    if write_snapshot:
        _write_snapshot(qrels, len(corpus_rows))

    return qrels, relevant_ids


def _write_snapshot(qrels: dict[str, dict[str, int]], corpus_size: int) -> None:
    EVAL_DIR.mkdir(exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_size": corpus_size,
        "query_count": len(qrels),
        "relevant_counts": {qid: len(rels) for qid, rels in qrels.items()},
    }
    SNAPSHOT_PATH.write_text(json.dumps(payload, indent=2) + "\n")


def title_matches_hints(title: str, hints: tuple[str, ...]) -> bool:
    t = title.lower()
    return any(h.lower() in t for h in hints)


def gold_pass_at_k(result_titles: list[str], hints: tuple[str, ...], k: int = 5) -> bool:
    """True if any top-K result title matches a gold hint substring."""
    if not hints:
        return True
    for title in result_titles[:k]:
        if title_matches_hints(title, hints):
            return True
    return False
