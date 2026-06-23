#!/usr/bin/env python3
"""Autonomous refresh: harvest usage, retrain the reranker, guard the held-out.

Guardrail checks (frozen curated set):
  - mean nDCG@10 did not drop
  - mean recall@10 did not drop by >2%
  - gold-subset pass@5 did not drop
  - no single query nDCG drop >0.15

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


async def main() -> None:
    from scripts.eval_metrics import measure_curated

    print("== 1. harvest usage ==")
    print(_run("harvest_eval.py"))

    before = await measure_curated() if MODEL.exists() else None
    if before:
        print(
            f"curated before: nDCG@10={before.ndcg:.3f}  "
            f"recall@10={before.recall:.3f}  gold={before.gold_pass_rate:.1%}"
        )
    if MODEL.exists():
        shutil.copy(MODEL, BACKUP)

    print("== 2. retrain reranker ==")
    print(_run("train_ltr.py"))

    after = await measure_curated()
    print(
        f"curated after:  nDCG@10={after.ndcg:.3f}  "
        f"recall@10={after.recall:.3f}  gold={after.gold_pass_rate:.1%}"
    )

    rollback = before is not None and BACKUP.exists() and after.regressed_vs(before)
    if rollback:
        shutil.copy(BACKUP, MODEL)
        print("REGRESSION -> rolled back:")
        for reason in rollback:
            print(f"  - {reason}")
    else:
        print("Adopted refreshed model (passed stricter guardrail).")
    if BACKUP.exists():
        BACKUP.unlink()


if __name__ == "__main__":
    asyncio.run(main())
