"""Map arXiv API entries to research_paper artifacts."""
from __future__ import annotations

from typing import Any

from .paths import *  # noqa: F403

from app.services.extraction_service import build_embedding_text, infer_fields_from_text
from app.services.embedding_service import embed_text
from app.services.scoring_service import score_all
from app.utils.text import slugify, truncate
from app.utils.urls import canonicalize_url


def arxiv_entry_to_artifact(entry: dict[str, Any]) -> dict[str, Any]:
    title = entry.get("title", "").replace("\n", " ").strip()
    abstract = entry.get("summary", "").replace("\n", " ").strip()
    arxiv_id = entry.get("id", "")
    url = arxiv_id if arxiv_id.startswith("http") else f"https://arxiv.org/abs/{arxiv_id.split('/')[-1]}"
    has_code = "github" in abstract.lower() or "github" in title.lower()

    inferred = infer_fields_from_text(title, abstract, abstract)
    practical = (
        "This may help builders working on agents, RAG, code generation, or efficient inference "
        "who want a research-backed approach to reference."
    )

    artifact: dict[str, Any] = {
        "title": title[:300],
        "slug": slugify(title),
        "source_type": "arxiv",
        "artifact_type": "research_paper",
        "source_url": url,
        "canonical_url": canonicalize_url(url),
        "summary": truncate(abstract, 600),
        "what_it_helps_build": practical,
        "technical_core": truncate(abstract, 800),
        "practical_use_case": practical,
        "how_to_remix": (
            "Read the abstract and method section, check for a linked code repo, "
            "then port the technique into your stack."
        ),
        "tags": inferred.get("tags", []) + ["arxiv", "research"],
        "tools": inferred.get("tools", []),
        "frameworks": inferred.get("frameworks", []),
        "languages": inferred.get("languages", []),
        "has_code": has_code,
        "has_paper": True,
        "has_docs": True,
        "popularity_score": 10,
    }
    score_all(artifact)
    # Papers without code are harder to remix.
    artifact["remixability_score"] = min(artifact.get("remixability_score", 0), 45 if not has_code else 70)
    artifact["hype_risk_score"] = max(artifact.get("hype_risk_score", 0), 25)
    artifact["embedding_vector"] = embed_text(build_embedding_text(artifact))
    return artifact
