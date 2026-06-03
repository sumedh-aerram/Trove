"""Submission moderation: auto-approve high quality, pending otherwise."""
from __future__ import annotations

from typing import Any


def moderate_submission(artifact: dict[str, Any]) -> dict[str, Any]:
    """Decide post status based on quality and hype scores."""
    quality = float(artifact.get("quality_score") or 0)
    hype = float(artifact.get("hype_risk_score") or 0)

    quality_explanation = (
        f"Quality score {quality:.0f}/100 based on clarity, reproducibility, and technical specificity."
    )
    hype_explanation = (
        f"Hype risk {hype:.0f}/100 — lower is better. High scores mean vague marketing or missing code."
    )

    if quality >= 70 and hype <= 45:
        return {
            "status": "approved",
            "moderation_reason": "Auto-approved: strong quality, low hype risk.",
            "quality_explanation": quality_explanation,
            "hype_explanation": hype_explanation,
        }

    reasons: list[str] = []
    if quality < 70:
        reasons.append("quality below auto-approve threshold (70)")
    if hype > 45:
        reasons.append("hype risk above auto-approve threshold (45)")

    return {
        "status": "pending",
        "moderation_reason": "Pending review: " + "; ".join(reasons),
        "quality_explanation": quality_explanation,
        "hype_explanation": hype_explanation,
    }
