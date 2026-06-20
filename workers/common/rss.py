"""Map RSS/Atom feed entries (builder + AI-eng blogs) to article artifacts.

These are long-form, high-substance write-ups: architectures, how-tos, post
mortems. Good "how do I build / integrate X" material to balance the index.
"""
from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Optional

from .paths import *  # noqa: F403

from app.services.embedding_service import embed_text
from app.services.extraction_service import build_embedding_text, infer_fields_from_text
from app.services.scoring_service import score_all
from app.utils.text import slugify, truncate
from app.utils.urls import canonicalize_url

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def parse_date(raw: Optional[str]) -> Optional[datetime]:
    """Feeds use RFC822 (RSS) or ISO 8601 (Atom); return a datetime or None."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        return parsedate_to_datetime(raw)  # RFC822, e.g. "Thu, 18 Jun 2026 ..."
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def strip_html(text: str) -> str:
    text = _TAG_RE.sub(" ", text or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return _WS_RE.sub(" ", text).strip()


def rss_entry_to_artifact(entry: dict[str, Any], feed_name: str) -> dict[str, Any]:
    title = strip_html(entry.get("title", ""))[:300]
    link = entry.get("link", "")
    body = strip_html(entry.get("summary", ""))

    inferred = infer_fields_from_text(title, body, body)
    help_line = (
        f"A write-up from {feed_name} you can learn an approach or integration "
        "pattern from, then adapt to your own stack."
    )

    artifact: dict[str, Any] = {
        "title": title,
        "slug": slugify(title),
        "source_type": "rss",
        "artifact_type": "article",
        "source_url": link,
        "canonical_url": canonicalize_url(link),
        "author_name": feed_name,
        "summary": truncate(body, 600),
        "what_it_helps_build": help_line,
        "technical_core": truncate(body, 800),
        "practical_use_case": help_line,
        "how_to_remix": "Read the post for the approach, then port the relevant pattern into your project.",
        "tags": inferred.get("tags", []) + ["blog", "article"],
        "tools": inferred.get("tools", []),
        "frameworks": inferred.get("frameworks", []),
        "languages": inferred.get("languages", []),
        "has_code": "github.com" in body.lower() or "```" in body,
        "has_docs": True,
        "published_at": parse_date(entry.get("published")),
        "popularity_score": 12,
    }
    score_all(artifact)
    artifact["embedding_vector"] = embed_text(build_embedding_text(artifact))
    return artifact
