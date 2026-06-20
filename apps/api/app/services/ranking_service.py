"""Hybrid ranking: RRF fusion + metadata-weighted final score + why_relevant."""
from __future__ import annotations

import re
from typing import Any

from ..utils.dates import recency_score

RRF_K = 60


def normalize_score(value: float | None, max_val: float = 100.0) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value) / max_val))


def reciprocal_rank_fusion(
    *ranked_lists: list[dict[str, Any]],
    weights: list[float] | None = None,
) -> dict[str, float]:
    """Fuse N ranked lists with weighted RRF: sum(weight / (k + rank))."""
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    rrf: dict[str, float] = {}
    for ranked, weight in zip(ranked_lists, weights):
        for rank, item in enumerate(ranked, start=1):
            aid = str(item["id"])
            rrf[aid] = rrf.get(aid, 0.0) + weight * (1.0 / (RRF_K + rank))
    return rrf


def artifact_text_blob(artifact: dict[str, Any]) -> str:
    """Single lowercase blob for phrase / keyword matching."""
    parts = [
        artifact.get("title") or "",
        artifact.get("summary") or "",
        artifact.get("what_it_helps_build") or "",
        artifact.get("technical_core") or "",
        artifact.get("how_to_remix") or "",
        " ".join(artifact.get("tags") or []),
        " ".join(artifact.get("tools") or []),
        " ".join(artifact.get("frameworks") or []),
        " ".join(artifact.get("languages") or []),
        artifact.get("artifact_type") or "",
    ]
    return " ".join(parts).lower()


def collect_intent_matches(artifact: dict[str, Any], intent: dict[str, Any]) -> dict[str, list[str]]:
    """What intent dimensions matched this artifact."""
    blob = artifact_text_blob(artifact)
    matches: dict[str, list[str]] = {
        "frameworks": [],
        "tools": [],
        "languages": [],
        "tags": [],
        "terms": [],
        "phrases": [],
    }

    def actual_set(key: str) -> set[str]:
        return {x.lower() for x in (artifact.get(key) or [])}

    for fw in intent.get("frameworks", []):
        if fw.lower() in actual_set("frameworks") or fw.lower().replace(" ", "") in blob.replace(" ", ""):
            matches["frameworks"].append(fw)

    for tool in intent.get("tools", []):
        if tool.lower() in actual_set("tools") or tool.lower() in blob:
            matches["tools"].append(tool)

    for lang in intent.get("languages", []):
        if lang.lower() in actual_set("languages") or lang.lower() in blob:
            matches["languages"].append(lang)

    for tag in intent.get("tags", []):
        tl = tag.lower()
        if tl in {t.lower() for t in (artifact.get("tags") or [])} or tl in blob:
            matches["tags"].append(tag)

    for term in intent.get("search_terms", []):
        tl = term.lower()
        if len(tl) >= 3 and tl in blob:
            matches["terms"].append(term)

    phrase_checks = [
        ("chrome extension", ("chrome", "extension")),
        ("browser extension", ("browser", "extension")),
        ("rag", ("rag", "retrieval")),
        ("research paper", ("paper", "research", "arxiv")),
        ("pdf", ("pdf",)),
        ("mcp server", ("mcp",)),
        ("coding agent", ("coding", "agent")),
        ("lecture", ("lecture",)),
        ("quiz", ("quiz",)),
        ("posture", ("posture", "pose")),
        ("computer vision", ("vision", "computer")),
    ]
    for label, needles in phrase_checks:
        if any(n in blob for n in needles):
            if any(n in " ".join(intent.get("search_terms", [])) or n in intent.get("project_type", "") for n in needles):
                matches["phrases"].append(label)

    return matches


def project_relevance_score(
    artifact: dict[str, Any],
    intent: dict[str, Any],
    *,
    kw_rank: float | None = None,
    vec_similarity: float | None = None,
) -> float:
    """0-1 score: how well artifact matches extracted project intent."""
    matches = collect_intent_matches(artifact, intent)
    blob = artifact_text_blob(artifact)
    score = 0.0
    weight_sum = 0.0

    def add(weight: float, value: float) -> None:
        nonlocal score, weight_sum
        score += weight * value
        weight_sum += weight

    # Structured metadata overlap.
    for key, w in (("frameworks", 0.18), ("tools", 0.18), ("tags", 0.14), ("languages", 0.08)):
        desired = intent.get(key, [])
        if not desired:
            continue
        hit = len(matches[key])
        add(w, min(1.0, hit / max(1, min(len(desired), 4))))

    # Search term hits in blob.
    terms = intent.get("search_terms", [])
    if terms:
        term_hits = sum(1 for t in terms[:20] if t.lower() in blob)
        add(0.22, min(1.0, term_hits / max(2, min(len(terms), 8))))

    # Artifact type preference.
    desired_types = {t.lower() for t in intent.get("desired_artifact_types", [])}
    if desired_types:
        at = (artifact.get("artifact_type") or "").lower()
        add(0.08, 1.0 if at in desired_types else 0.2)

    # Project-type keyword profile.
    profiles: dict[str, tuple[str, ...]] = {
        "rag_browser_research": ("rag", "extension", "chrome", "browser", "paper", "arxiv", "pdf"),
        "education_media": ("lecture", "quiz", "video", "summarizer", "whisper", "flashcard"),
        "coding_agent_tooling": ("mcp", "cursor", "claude", "agent", "workflow"),
        "computer_vision": ("vision", "pose", "posture", "webcam", "mediapipe", "hackathon"),
        "rag_research": ("rag", "retrieval", "arxiv", "paper", "vector"),
        "browser_extension": ("extension", "chrome", "browser"),
    }
    ptype = intent.get("project_type", "")
    if ptype in profiles:
        kws = profiles[ptype]
        hits = sum(1 for k in kws if k in blob)
        add(0.12, min(1.0, hits / max(2, len(kws) // 2)))

    # Retrieval signals.
    if kw_rank is not None:
        add(0.12, min(1.0, float(kw_rank) * 8.0))
    if vec_similarity is not None:
        add(0.15, max(0.0, min(1.0, float(vec_similarity))))

    if weight_sum == 0:
        return 0.0
    return min(1.0, score / weight_sum)


def substance_score(artifact: dict[str, Any]) -> float:
    """How much real, reusable substance an artifact has (0-1).

    Rewards runnable code + setup + a real write-up; penalizes bare link posts
    (e.g. low-signal Hacker News items) that crowd out genuinely buildable work.
    """
    s = 0.0
    if artifact.get("has_code"):
        s += 0.4
    if artifact.get("setup_commands") or artifact.get("implementation_steps"):
        s += 0.3
    text = " ".join(
        str(artifact.get(k) or "")
        for k in ("summary", "what_it_helps_build", "technical_core")
    )
    if len(text) >= 120:
        s += 0.3
    return min(1.0, s)


def compute_final_score(
    artifact: dict[str, Any],
    intent: dict[str, Any],
    rrf_score: float,
    *,
    project_relevance: float | None = None,
) -> float:
    """Weighted blend per product spec (scores normalized 0-1)."""
    rel = project_relevance if project_relevance is not None else project_relevance_score(artifact, intent)
    remix = normalize_score(artifact.get("remixability_score"))
    quality = normalize_score(artifact.get("quality_score"))
    underground = normalize_score(artifact.get("underground_score"))
    recency = recency_score(artifact.get("published_at"))
    popularity = normalize_score(artifact.get("popularity_score"))
    hype = normalize_score(artifact.get("hype_risk_score"))
    substance = substance_score(artifact)
    rrf_norm = min(1.0, rrf_score * 45)

    final = (
        0.40 * rel
        + 0.10 * rrf_norm
        + 0.18 * remix
        + 0.14 * quality
        + 0.08 * underground
        + 0.08 * recency
        + 0.03 * popularity
        + 0.12 * substance
        - 0.10 * hype
    )
    return max(0.0, min(1.0, final))


def build_why_relevant(artifact: dict[str, Any], intent: dict[str, Any]) -> str:
    """Narrative explanation tailored to project context."""
    matches = collect_intent_matches(artifact, intent)
    blob = artifact_text_blob(artifact)
    ptype = intent.get("project_type", "general")

    has_ext = any(x in blob for x in ("extension", "chrome", "browser"))
    has_rag = any(x in blob for x in ("rag", "retrieval", "vector"))
    has_paper = any(x in blob for x in ("paper", "arxiv", "pdf", "research"))
    has_lecture = any(x in blob for x in ("lecture", "quiz", "video", "summarizer"))
    has_mcp = "mcp" in blob
    has_cv = any(x in blob for x in ("vision", "posture", "pose", "webcam"))

    # Composite narratives for common project-context patterns.
    if ptype == "rag_browser_research" or (has_ext and has_rag and has_paper):
        return (
            "Matches your project because it combines browser extension architecture "
            "with RAG over research papers."
        )
    if has_ext and has_rag:
        return (
            "Matches your project because it is a browser extension that uses "
            "retrieval-augmented generation."
        )
    if ptype == "education_media" or (has_lecture and has_rag):
        return (
            "Matches your project because it targets lecture/video content with "
            "summarization and study features you can remix."
        )
    if ptype == "coding_agent_tooling" or has_mcp:
        parts = ["Matches your project because it provides MCP or coding-agent tooling"]
        if matches["tools"]:
            parts.append(f"using {', '.join(matches['tools'][:2])}")
        return " ".join(parts) + "."

    if ptype == "computer_vision" or has_cv:
        return (
            "Matches your project because it applies computer vision (e.g. pose/webcam) "
            "in a hackathon-style app you can fork."
        )

    # Stack-based narrative.
    highlights: list[str] = []
    if matches["frameworks"]:
        highlights.append(", ".join(matches["frameworks"][:3]))
    if matches["tools"]:
        highlights.append(", ".join(matches["tools"][:3]))
    if matches["tags"]:
        highlights.append("tags: " + ", ".join(matches["tags"][:3]))

    extras: list[str] = []
    if artifact.get("setup_commands") or artifact.get("implementation_steps"):
        extras.append("includes setup steps you can remix")
    if artifact.get("has_code"):
        extras.append("ships with open-source code")

    if highlights:
        msg = "Matches your project because it uses " + "; ".join(highlights)
        if extras:
            msg += " and " + ", ".join(extras)
        return msg + "."

    if extras:
        return "Matches your project because it " + ", ".join(extras) + "."

    if artifact.get("summary"):
        return (
            "Matches your project because its summary and stack align with your "
            "full project-context query."
        )
    return "Matches your project based on semantic and keyword relevance to your query."
