"""asyncpg connection pool and helpers.

We use raw asyncpg (not an ORM) because the core queries are hybrid full-text +
pgvector searches that are far clearer as SQL than as ORM expressions.
"""
from __future__ import annotations

import json
from typing import Any, Optional

import asyncpg

from .config import get_settings

_pool: Optional[asyncpg.Pool] = None


def _normalize_dsn(url: str) -> str:
    # asyncpg does not understand the SQLAlchemy-style +driver suffix or the
    # postgresql+asyncpg scheme, so strip it if present.
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgres+asyncpg://", "postgresql://"
    )


async def _init_connection(conn: asyncpg.Connection) -> None:
    # Return jsonb as parsed Python objects and accept Python objects on write.
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    # Raise HNSW search effort for better vector recall (session-level GUC).
    try:
        ef = get_settings().hnsw_ef_search
        await conn.execute(f"SET hnsw.ef_search = {int(ef)}")
    except Exception:  # noqa: BLE001 — older pgvector without the GUC
        pass


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            dsn=_normalize_dsn(settings.database_url),
            min_size=1,
            max_size=10,
            init=_init_connection,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_pool() first.")
    return _pool


async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    async with get_pool().acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args: Any) -> Optional[asyncpg.Record]:
    async with get_pool().acquire() as conn:
        return await conn.fetchrow(query, *args)


async def execute(query: str, *args: Any) -> str:
    async with get_pool().acquire() as conn:
        return await conn.execute(query, *args)
