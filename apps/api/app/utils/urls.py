"""URL canonicalization and validation."""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse

# Tracking params we always drop during canonicalization.
_TRACKING_PREFIXES = ("utm_", "ref", "fbclid", "gclid")


def canonicalize_url(url: str | None) -> str | None:
    """Normalize a URL so duplicates collapse to the same canonical_url.

    - lowercases scheme + host
    - forces https
    - strips default ports, trailing slashes, fragments, tracking query params
    """
    if not url:
        return None
    url = url.strip()
    if "://" not in url:
        url = "https://" + url

    parsed = urlparse(url)
    scheme = "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    netloc = netloc.replace(":80", "").replace(":443", "")

    path = parsed.path.rstrip("/")

    # Drop tracking query params; keep meaningful ones.
    query_parts = []
    if parsed.query:
        for part in parsed.query.split("&"):
            key = part.split("=", 1)[0].lower()
            if any(key.startswith(p) for p in _TRACKING_PREFIXES):
                continue
            query_parts.append(part)
    query = "&".join(query_parts)

    return urlunparse((scheme, netloc, path, "", query, ""))


def looks_like_valid_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url if "://" in url else "https://" + url)
    return bool(parsed.netloc) and "." in parsed.netloc
