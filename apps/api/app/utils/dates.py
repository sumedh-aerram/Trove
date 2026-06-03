"""Date helpers for scoring and recency."""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def recency_score(published_at: datetime | str | None, window_days: int = 180) -> float:
    """Return 0-1 score based on how recently the artifact was published/updated."""
    if published_at is None:
        return 0.3
    if isinstance(published_at, str):
        published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_days = (utcnow() - published_at).days
    if age_days <= 0:
        return 1.0
    if age_days >= window_days:
        return 0.0
    return max(0.0, 1.0 - age_days / window_days)
