"""Map Hacker News Algolia hits to BuildArtifacts."""
from __future__ import annotations

from typing import Any

from .paths import *  # noqa: F403

from app.services.extraction_service import infer_fields_from_text, infer_artifact_type, build_embedding_text
from app.services.embedding_service import embed_text
from app.services.scoring_service import score_all
from app.utils.text import slugify
from app.utils.urls import canonicalize_url


def hn_hit_to_artifact(hit: dict[str, Any]) -> dict[str, Any]:
    title = hit.get("title") or hit.get("story_title") or "HN post"
    url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
    canonical = canonicalize_url(url) or url
    combined = f"{title}\n{url}"
    inferred = infer_fields_from_text(title, "", combined)

    has_github = "github.com" in url.lower()
    artifact: dict[str, Any] = {
        "title": title[:200],
        "slug": slugify(title),
        "source_type": "hackernews",
        "artifact_type": (
            "open_source_project" if has_github else infer_artifact_type(title)
        ),
        "source_url": url,
        "canonical_url": canonical,
        "author_name": hit.get("author"),
        "summary": title,
        "what_it_helps_build": f"Discussed on Hacker News: {title}",
        "technical_core": title,
        "practical_use_case": "Builders tracking trending tools and launch posts.",
        "how_to_remix": "Follow the linked repo or discussion and adapt the approach.",
        "tags": inferred.get("tags", []) + ["hackernews"],
        "tools": inferred.get("tools", []),
        "frameworks": inferred.get("frameworks", []),
        "languages": inferred.get("languages", []),
        "apis": inferred.get("apis", []),
        "models": inferred.get("models", []),
        "has_code": has_github,
        "has_docs": False,
        "has_demo": False,
        "has_paper": "arxiv" in url.lower(),
        "has_license": False,
        "popularity_score": min(100, int(hit.get("points") or 0)),
    }
    if not has_github:
        artifact["hype_risk_score"] = 55  # discussion-only posts are riskier
    score_all(artifact)
    artifact["embedding_vector"] = embed_text(build_embedding_text(artifact))
    return artifact
