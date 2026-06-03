"""Text helpers: slugify, cleaning, and pgvector formatting."""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Sequence


def slugify(value: str, max_length: int = 80) -> str:
    """Turn an arbitrary string into a URL-safe slug."""
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    value = re.sub(r"-{2,}", "-", value)
    return value[:max_length] or "artifact"


def clean_text(text: str | None) -> str:
    """Light cleanup of markdown/README text for storage and embedding."""
    if not text:
        return ""
    # Strip code fences markers but keep inner text, drop images, collapse space.
    text = re.sub(r"```[a-zA-Z0-9]*\n", "", text)
    text = text.replace("```", "")
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)  # images
    text = re.sub(r"<[^>]+>", " ", text)  # html tags
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate(text: str | None, max_chars: int) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


def to_pgvector(values: Sequence[float] | None) -> str | None:
    """Format an embedding as a pgvector literal: '[0.1,0.2,...]'."""
    if values is None:
        return None
    return "[" + ",".join(f"{float(v):.6f}" for v in values) + "]"


def dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        low = key.lower()
        if key and low not in seen:
            seen.add(low)
            out.append(key)
    return out
