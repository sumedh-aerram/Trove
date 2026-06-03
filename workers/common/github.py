"""Map GitHub repository JSON + README into a BuildArtifact dict."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .paths import *  # noqa: F403 — ensures apps/api on path

from app.services.extraction_service import (  # noqa: E402
    build_embedding_text,
    infer_artifact_type,
    infer_fields_from_text,
)
from app.services.embedding_service import embed_text  # noqa: E402
from app.services.scoring_service import score_all  # noqa: E402
from app.utils.text import clean_text, dedupe_keep_order, slugify, truncate  # noqa: E402
from app.utils.urls import canonicalize_url  # noqa: E402


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _first_readme_paragraph(readme: str) -> str:
    """First non-heading, non-badge paragraph from README."""
    for block in re.split(r"\n\s*\n", readme):
        lines = []
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("!["):
                continue
            if line.startswith(("[!", "<", "|")):
                continue
            lines.append(line)
        text = " ".join(lines).strip()
        if len(text) > 40:
            return truncate(text, 400)
    return ""


def _infer_practical_use_case(description: str, readme: str, artifact_type: str) -> str:
    lower = f"{description}\n{readme[:1500]}".lower()
    if "hackathon" in lower:
        return "Hackathon builders and weekend hackers shipping a demo fast."
    if artifact_type == "mcp_server":
        return "Developers wiring tools into Claude Code, Cursor, Cline, or custom agents."
    if artifact_type == "coding_agent_workflow":
        return "Teams standardizing how their coding agent runs repeatable workflows."
    if artifact_type == "starter_template":
        return "Indie hackers and vibe coders who want a forkable starter instead of a blank repo."
    if "extension" in lower or "chrome" in lower:
        return "Builders making browser extensions with AI features."
    if any(w in lower for w in ("lecture", "video", "transcri", "whisper")):
        return "Edtech and media builders automating transcripts, summaries, or study tools."
    if "rag" in lower or "retrieval" in lower:
        return "Builders adding RAG, search, or Q&A over documents to their app."
    return "Full-stack builders and vibe coders looking for a remixable open-source starting point."


def _infer_how_to_remix(readme: str, setup_commands: list[str]) -> str:
    if setup_commands:
        return (
            "Clone the repo, run the setup commands below, then replace the model provider "
            "and UI layer while keeping the core pipeline."
        )
    if re.search(r"(?i)##\s*usage", readme):
        return "Follow the Usage section in the README, then adapt prompts and data sources for your app."
    return (
        "Clone the repo, copy the modules you need, and rewire configuration for your stack."
    )


def _normalize_topics(topics: list[str]) -> list[str]:
    return [t.lower().replace(" ", "-") for t in topics if t]


def _popularity_score(stars: int, forks: int) -> float:
    return min(100.0, (max(stars, 0) ** 0.5) * 2.0 + min(max(forks, 0), 500) / 50.0)


def repo_to_artifact(repo: dict[str, Any], readme: str = "") -> dict[str, Any]:
    """Convert GitHub search/repo API payload + README into a BuildArtifact dict."""
    full_name = repo.get("full_name") or repo.get("name", "unknown/repo")
    description = (repo.get("description") or "").strip()
    cleaned = clean_text(readme)
    inferred = infer_fields_from_text(full_name, description, readme)

    topics = _normalize_topics(repo.get("topics") or [])
    tags = dedupe_keep_order([*(inferred.get("tags") or []), *topics])

    languages = list(inferred.get("languages") or [])
    gh_lang = repo.get("language")
    if gh_lang and gh_lang not in languages:
        languages.insert(0, gh_lang)

    stars = int(repo.get("stargazers_count") or 0)
    forks = int(repo.get("forks_count") or 0)
    homepage = (repo.get("homepage") or "").strip()
    readme_lower = readme.lower()
    has_demo = bool(homepage) or any(
        w in readme_lower for w in ("demo", "live at", "vercel.app", "netlify.app")
    )

    license_info = repo.get("license")
    license_spdx = None
    if isinstance(license_info, dict):
        license_spdx = license_info.get("spdx_id")

    combined_type_text = f"{full_name}\n{description}\n{readme[:3000]}"
    artifact_type = infer_artifact_type(combined_type_text)

    summary = description or _first_readme_paragraph(readme) or truncate(cleaned, 280)
    what_build = (
        description
        if description
        else truncate(cleaned, 220) or f"Open-source repo: {full_name}"
    )

    artifact: dict[str, Any] = {
        "title": full_name,
        "slug": slugify(full_name),
        "source_type": "github",
        "artifact_type": artifact_type,
        "source_url": repo.get("html_url", f"https://github.com/{full_name}"),
        "canonical_url": canonicalize_url(repo.get("html_url")),
        "author_name": (repo.get("owner") or {}).get("login"),
        "author_url": (repo.get("owner") or {}).get("html_url"),
        "raw_text": readme[:50_000] if readme else None,
        "clean_text": cleaned[:20_000] if cleaned else None,
        "summary": summary,
        "what_it_helps_build": f"Helps you build: {what_build}" if not what_build.startswith("Helps") else what_build,
        "technical_core": truncate(cleaned, 600) if cleaned else description,
        "practical_use_case": _infer_practical_use_case(description, readme, artifact_type),
        "how_to_remix": _infer_how_to_remix(readme, inferred.get("setup_commands", [])),
        "implementation_steps": inferred.get("implementation_steps", []),
        "setup_commands": inferred.get("setup_commands", []),
        "tags": tags[:30],
        "tools": dedupe_keep_order(inferred.get("tools", [])),
        "frameworks": dedupe_keep_order(inferred.get("frameworks", [])),
        "languages": dedupe_keep_order(languages),
        "apis": dedupe_keep_order(inferred.get("apis", [])),
        "models": dedupe_keep_order(inferred.get("models", [])),
        "has_code": not repo.get("disabled", False),
        "has_demo": has_demo,
        "has_docs": bool(readme and len(readme) > 80),
        "has_paper": any(w in readme_lower for w in ("arxiv", "research paper", "benchmark")),
        "has_license": bool(license_spdx),
        "license": license_spdx,
        "published_at": _parse_dt(repo.get("pushed_at") or repo.get("updated_at") or repo.get("created_at")),
        "popularity_score": _popularity_score(stars, forks),
        "github_stars": stars,
        "github_forks": forks,
    }

    score_all(artifact, stars=stars)
    artifact["embedding_vector"] = embed_text(build_embedding_text(artifact))
    return artifact
