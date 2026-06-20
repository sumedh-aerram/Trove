#!/usr/bin/env python3
"""Autonomous refresh: harvest usage, retrain the reranker, guard the held-out.

This is the loop's heartbeat, meant for cron (see workers/crontab.example):

  1. Harvest search_events -> grown eval queries + feedback pairs.
  2. Back up the current LTR model.
  3. Retrain on curated + harvested data (train_ltr.py also nested-CV validates
     and only saves if it beats the linear blend).
  4. Guardrail: re-run the eval on the FROZEN curated set. If curated nDCG@10
     regressed versus the backup, roll back. The loop can grow coverage but can
     never quietly make the held-out anchor worse.

Run (from apps/api):
  DATABASE_URL=... PYTHONPATH=. python scripts/refresh_models.py
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_DIR = Path(__file__).resolve().parents[1]
MODEL = API_DIR / "app" / "services" / "ltr_model.txt"
BACKUP = API_DIR / "app" / "services" / "ltr_model.bak.txt"


def _run(script: str) -> str:
    """Run a sibling script in-process env; return stdout."""
    proc = subprocess.run(
        [sys.executable, "-u", str(API_DIR / "scripts" / script)],
        cwd=str(API_DIR),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"{script} failed")
    return proc.stdout


async def curated_ndcg() -> float:
    """nDCG@10 on the FROZEN curated set only (clean held-out anchor)."""
    from app.db import close_pool, init_pool
    from app.services.search_service import hybrid_search
    from scripts.eval_search import EVALSET, build_oracle_qrels
    from scripts.tune_search import ndcg_at_k

    await init_pool()
    try:
        qrels, _ = await build_oracle_qrels(EVALSET)  # curated only, no overlay
        vals = []
        for i, (q, _t) in enumerate(EVALSET):
            res = await hybrid_search(q, limit=20)
            ranked = [str(r["id"]) for r in res["results"]]
            vals.append(ndcg_at_k(ranked, qrels[f"q{i}"]))
        return sum(vals) / len(vals) if vals else 0.0
    finally:
        await close_pool()


async def main() -> None:
    print("== 1. harvest usage ==")
    print(_run("harvest_eval.py"))

    before = await curated_ndcg() if MODEL.exists() else 0.0
    if MODEL.exists():
        shutil.copy(MODEL, BACKUP)
    print(f"curated held-out nDCG@10 before: {before:.3f}")

    print("== 2. retrain reranker ==")
    print(_run("train_ltr.py"))

    after = await curated_ndcg()
    print(f"curated held-out nDCG@10 after:  {after:.3f}")

    if after + 1e-6 < before and BACKUP.exists():
        shutil.copy(BACKUP, MODEL)
        print(f"REGRESSION ({after:.3f} < {before:.3f}) -> rolled back to previous model.")
    else:
        print("Adopted refreshed model (held-out did not regress).")
    if BACKUP.exists():
        BACKUP.unlink()


if __name__ == "__main__":
    asyncio.run(main())
