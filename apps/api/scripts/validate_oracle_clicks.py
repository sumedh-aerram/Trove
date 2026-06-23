#!/usr/bin/env python3
"""Compare click/star labels against the term oracle (find grading gaps).

Run (from apps/api):
  DATABASE_URL=... PYTHONPATH=. python scripts/validate_oracle_clicks.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db  # noqa: E402
from app.db import close_pool, init_pool  # noqa: E402
from scripts.eval_data import load_feedback_pairs  # noqa: E402
from scripts.eval_oracle import MIN_GRADE_POINTS, build_oracle_qrels, grade_row  # noqa: E402
from scripts.eval_queries import EVALSET  # noqa: E402


async def main() -> None:
    pairs = load_feedback_pairs()
    if not pairs:
        print("No feedback_pairs.json yet — run harvest_eval.py after some usage.")
        return

    await init_pool()
    try:
        qrels, _ = await build_oracle_qrels(EVALSET)
        qid_by_query = {q.lower(): f"q{i}" for i, (q, _) in enumerate(EVALSET)}

        rows = await db.fetch(
            "SELECT id, title, summary, what_it_helps_build, technical_core, "
            "tags, tools, frameworks, languages FROM artifacts"
        )
        by_id = {str(r["id"]): dict(r) for r in rows}

        covered = 0
        oracle_miss = 0
        for p in pairs:
            q = str(p.get("query", ""))
            pid = str(p.get("positive_id", ""))
            qid = qid_by_query.get(q.lower())
            if not qid:
                continue
            covered += 1
            grade = qrels.get(qid, {}).get(pid, 0)
            if grade <= 0:
                oracle_miss += 1
                art = by_id.get(pid, {})
                idx = int(qid[1:])
                raw = grade_row(art, EVALSET[idx][1]) if art else 0
                print(f"MISS  query={q[:55]!r}")
                print(f"      clicked={art.get('title', pid)}")
                print(f"      oracle_grade={raw} (need >={MIN_GRADE_POINTS})")

        print(f"\n{covered} click pairs overlap frozen eval queries.")
        print(f"{oracle_miss} clicks on docs the oracle grades as irrelevant.")
        if oracle_miss:
            print("Consider adding terms to those eval queries in eval_queries.py.")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
