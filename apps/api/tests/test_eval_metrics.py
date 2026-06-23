"""Unit tests for eval metrics helpers (no database)."""
from __future__ import annotations

from scripts.eval_math import recall_at_k
from scripts.eval_metrics import CuratedEvalReport


def test_recall_at_k():
    rels = {"a": 2, "b": 1, "c": 1}
    assert recall_at_k(["a", "x", "b", "y"], rels, k=3) == 2 / 3


def test_regression_detects_ndcg_drop():
    before = CuratedEvalReport(0.6, 0.5, 1.0, [0.6, 0.6], [0.5, 0.5], [])
    after = CuratedEvalReport(0.5, 0.5, 1.0, [0.5, 0.5], [0.5, 0.5], [])
    assert after.regressed_vs(before)


def test_regression_ignores_small_change():
    before = CuratedEvalReport(0.6, 0.5, 1.0, [0.6, 0.6], [0.5, 0.5], [])
    after = CuratedEvalReport(0.6, 0.49, 1.0, [0.6, 0.6], [0.49, 0.49], [])
    assert not after.regressed_vs(before)
