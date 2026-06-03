"""Row -> dict helpers for asyncpg records."""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

import asyncpg


def _uuid_str(value: Any) -> str:
    if isinstance(value, UUID):
        return str(value)
    return str(value)


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def record_to_artifact(row: asyncpg.Record) -> dict[str, Any]:
    """Convert a DB row into a JSON-serializable artifact dict."""
    data = {k: _serialize_value(v) for k, v in dict(row).items()}
    if "id" in data and data["id"] is not None:
        data["id"] = _uuid_str(data["id"])
    for key in ("implementation_steps", "setup_commands"):
        if key in data and data[key] is None:
            data[key] = []
    for key in ("tags", "domains", "tools", "languages", "frameworks", "apis", "models"):
        if key in data and data[key] is None:
            data[key] = []
    # Never expose raw embedding vectors in API responses.
    data.pop("embedding", None)
    data.pop("search_vector", None)
    return data


def record_to_profile(row: asyncpg.Record) -> dict[str, Any]:
    data = dict(row)
    if "id" in data and data["id"] is not None:
        data["id"] = _uuid_str(data["id"])
    return data


def record_to_post(row: asyncpg.Record) -> dict[str, Any]:
    data = dict(row)
    for key in ("id", "author_id", "artifact_id"):
        if key in data and data[key] is not None:
            data[key] = _uuid_str(data[key])
    return data
