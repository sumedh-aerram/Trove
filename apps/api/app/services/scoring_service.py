"""Artifact scoring: quality, remixability, hype risk, applicability, underground."""
from __future__ import annotations

import re
from typing import Any

from ..utils.dates import recency_score
from ..utils.urls import looks_like_valid_url


def _clamp(score: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, score))


def _has_substance(text: str | None, min_len: int = 40) -> bool:
    return bool(text and len(text.strip()) >= min_len)


def _marketing_hype_signals(text: str) -> int:
    """Return hype penalty points from vague marketing language."""
    lower = text.lower()
    penalty = 0
    hype_phrases = (
        "10x", "revolutionary", "game-changing", "disrupt", "paradigm",
        "next generation", "world-class", "best-in-class", "unprecedented",
    )
    for phrase in hype_phrases:
        if phrase in lower:
            penalty += 20
            break
    if re.search(r"\b(ai|ml)\b", lower) and len(text) < 120:
        penalty += 10
    return penalty


def score_quality(artifact: dict[str, Any]) -> float:
    score = 0.0
    if _has_substance(artifact.get("what_it_helps_build")) or _has_substance(artifact.get("practical_use_case")):
        score += 20
    steps = artifact.get("implementation_steps") or []
    setup = artifact.get("setup_commands") or []
    if steps or setup:
        score += 20
    if artifact.get("has_code") or artifact.get("has_demo") or artifact.get("has_paper"):
        score += 15
    if _has_substance(artifact.get("technical_core")):
        score += 15
    if _has_substance(artifact.get("practical_use_case"), 25):
        score += 10
    if artifact.get("published_at") or artifact.get("last_crawled_at"):
        score += 10
    if artifact.get("has_demo") or (artifact.get("summary") and "example" in (artifact.get("summary") or "").lower()):
        score += 10
    return _clamp(score)


def score_remixability(artifact: dict[str, Any]) -> float:
    score = 0.0
    if artifact.get("has_code"):
        score += 20
    if artifact.get("has_docs"):
        score += 15
    if artifact.get("setup_commands"):
        score += 15
    common_fw = {"Next.js", "React", "FastAPI", "Supabase", "Tailwind", "Python", "TypeScript"}
    frameworks = set(artifact.get("frameworks") or [])
    if frameworks & common_fw:
        score += 15
    lic = (artifact.get("license") or "").lower()
    if artifact.get("has_license") and any(x in lic for x in ("mit", "apache", "bsd")):
        score += 10
    if _has_substance(artifact.get("how_to_remix"), 30):
        score += 10
    if artifact.get("has_demo"):
        score += 10
    if _has_substance(artifact.get("summary"), 20):
        score += 5
    return _clamp(score)


def score_hype_risk(artifact: dict[str, Any]) -> float:
    score = 0.0
    combined = " ".join(
        str(artifact.get(k) or "")
        for k in ("title", "summary", "what_it_helps_build", "technical_core", "how_to_remix")
    )
    score += _marketing_hype_signals(combined)
    if not artifact.get("has_code") and not artifact.get("has_demo") and not artifact.get("has_paper"):
        score += 20
    if not (artifact.get("implementation_steps") or artifact.get("setup_commands")):
        score += 15
    if _has_substance(combined, 200) is False and len(combined) > 20:
        score += 15
    if not looks_like_valid_url(artifact.get("source_url")):
        score += 10
    if not _has_substance(artifact.get("technical_core"), 30):
        score += 10
    title = (artifact.get("title") or "").lower()
    if len(title.split()) <= 3 and not artifact.get("has_code"):
        score += 10
    return _clamp(score)


def score_applicability(artifact: dict[str, Any]) -> float:
    score = 0.0
    if _has_substance(artifact.get("what_it_helps_build")):
        score += 25
    if artifact.get("has_code") or artifact.get("has_demo"):
        score += 20
    if artifact.get("frameworks") or artifact.get("tools"):
        score += 20
    if artifact.get("setup_commands") or artifact.get("implementation_steps"):
        score += 15
    if _has_substance(artifact.get("how_to_remix"), 25):
        score += 10
    if _has_substance(artifact.get("summary"), 30):
        score += 10
    return _clamp(score)


def score_underground(
    artifact: dict[str, Any],
    *,
    stars: int | None = None,
    niche_match: float = 0.5,
) -> float:
    """Reward useful, recent, niche artifacts that are not mega-hyped."""
    pop = artifact.get("popularity_score") or 0
    if stars is not None:
        low_star_bonus = max(0.0, 1.0 - min(stars, 2000) / 2000)
    else:
        # popularity_score is already 0-100 normalized from crawlers
        low_star_bonus = max(0.0, 1.0 - pop / 100.0)

    rec = recency_score(artifact.get("published_at"))
    quality_component = (artifact.get("quality_score") or score_quality(artifact)) / 100.0

    underground = 100.0 * (
        0.35 * low_star_bonus
        + 0.25 * rec
        + 0.25 * quality_component
        + 0.15 * niche_match
    )
    return _clamp(underground)


def score_all(artifact: dict[str, Any], **kwargs: Any) -> dict[str, float]:
    """Compute all scores and attach them to the artifact dict in-place."""
    quality = score_quality(artifact)
    remix = score_remixability(artifact)
    hype = score_hype_risk(artifact)
    applic = score_applicability(artifact)
    artifact["quality_score"] = quality
    artifact["remixability_score"] = remix
    artifact["hype_risk_score"] = hype
    artifact["applicability_score"] = applic
    artifact["underground_score"] = score_underground(artifact, **kwargs)
    return {
        "quality_score": quality,
        "remixability_score": remix,
        "hype_risk_score": hype,
        "applicability_score": applic,
        "underground_score": artifact["underground_score"],
    }
