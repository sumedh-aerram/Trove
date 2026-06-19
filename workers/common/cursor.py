"""Persisted rotation cursor so each crawl run covers different ground.

The daemon invokes crawlers repeatedly; without rotation they'd re-fetch the
same first N queries forever (a static index). This advances a per-source
offset on disk, so successive runs sweep the whole topic space and keep adding
new artifacts.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

_CURSOR_PATH = Path(__file__).resolve().parents[1] / ".crawl_cursor.json"


def _load() -> dict:
    try:
        return json.loads(_CURSOR_PATH.read_text())
    except Exception:  # noqa: BLE001
        return {}


def _save(data: dict) -> None:
    try:
        _CURSOR_PATH.write_text(json.dumps(data))
    except Exception:  # noqa: BLE001
        pass


def rotate(source: str, items: list[T], size: int) -> list[T]:
    """Return the next `size` items for `source`, advancing the saved offset."""
    if not items:
        return []
    size = max(1, min(size, len(items)))
    state = _load()
    offset = int(state.get(source, 0)) % len(items)
    window = [items[(offset + i) % len(items)] for i in range(size)]
    state[source] = (offset + size) % len(items)
    _save(state)
    return window


def window_size(env_key: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(env_key, str(default))))
    except ValueError:
        return default
