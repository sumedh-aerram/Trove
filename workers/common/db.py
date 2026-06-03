"""Async DB helpers for ingestion workers."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Literal

import asyncpg
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

logger = logging.getLogger(__name__)

UpsertResult = Literal["inserted", "updated", "skipped"]


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/build_radar")
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def get_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=get_database_url(), min_size=1, max_size=5)


def _unique_slug(base_slug: str, canonical_url: str) -> str:
    """Avoid slug collisions on insert."""
    suffix = hashlib.sha1(canonical_url.encode()).hexdigest()[:6]
    return f"{base_slug[:70]}-{suffix}"


def _jsonb_list(value: Any) -> str:
    """asyncpg jsonb columns need a JSON string, not a Python list."""
    if value is None:
        return "[]"
    if isinstance(value, str):
        return value
    return json.dumps(value)


async def upsert_artifact(
    conn: asyncpg.Connection,
    artifact: dict[str, Any],
    *,
    source_metadata: dict[str, Any] | None = None,
) -> UpsertResult:
    """Insert or update by canonical_url. Returns inserted | updated | skipped."""
    from app.utils.text import to_pgvector  # noqa: WPS433

    canonical = artifact.get("canonical_url")
    if not canonical:
        logger.warning("Skipping artifact without canonical_url: %s", artifact.get("title"))
        return "skipped"

    embedding_literal = to_pgvector(artifact.get("embedding_vector"))
    existing = await conn.fetchrow(
        "SELECT id, slug FROM artifacts WHERE canonical_url = $1",
        canonical,
    )

    columns = (
        "title", "slug", "source_type", "artifact_type", "source_url", "canonical_url",
        "author_name", "author_url", "raw_text", "clean_text", "summary",
        "what_it_helps_build", "technical_core", "practical_use_case", "how_to_remix",
        "implementation_steps", "setup_commands",
        "tags", "tools", "frameworks", "languages", "apis", "models",
        "has_code", "has_demo", "has_docs", "has_paper", "has_license", "license",
        "published_at", "quality_score", "remixability_score", "applicability_score",
        "underground_score", "hype_risk_score", "popularity_score", "embedding",
    )

    values = (
        artifact["title"],
        artifact["slug"],
        artifact["source_type"],
        artifact["artifact_type"],
        artifact["source_url"],
        canonical,
        artifact.get("author_name"),
        artifact.get("author_url"),
        artifact.get("raw_text"),
        artifact.get("clean_text"),
        artifact.get("summary"),
        artifact.get("what_it_helps_build"),
        artifact.get("technical_core"),
        artifact.get("practical_use_case"),
        artifact.get("how_to_remix"),
        _jsonb_list(artifact.get("implementation_steps", [])),
        _jsonb_list(artifact.get("setup_commands", [])),
        artifact.get("tags", []),
        artifact.get("tools", []),
        artifact.get("frameworks", []),
        artifact.get("languages", []),
        artifact.get("apis", []),
        artifact.get("models", []),
        artifact.get("has_code", False),
        artifact.get("has_demo", False),
        artifact.get("has_docs", False),
        artifact.get("has_paper", False),
        artifact.get("has_license", False),
        artifact.get("license"),
        artifact.get("published_at"),
        artifact.get("quality_score", 0),
        artifact.get("remixability_score", 0),
        artifact.get("applicability_score", 0),
        artifact.get("underground_score", 0),
        artifact.get("hype_risk_score", 0),
        artifact.get("popularity_score", 0),
        embedding_literal,
    )

    if existing:
        # values[5] is canonical_url — immutable dedupe key, not updated.
        update_vals = values[:5] + values[6:]
        await conn.execute(
            """
            UPDATE artifacts SET
                title = $2, slug = $3, source_type = $4, artifact_type = $5,
                source_url = $6, author_name = $7, author_url = $8,
                raw_text = $9, clean_text = $10, summary = $11,
                what_it_helps_build = $12, technical_core = $13,
                practical_use_case = $14, how_to_remix = $15,
                implementation_steps = $16::jsonb, setup_commands = $17::jsonb,
                tags = $18, tools = $19, frameworks = $20, languages = $21,
                apis = $22, models = $23,
                has_code = $24, has_demo = $25, has_docs = $26, has_paper = $27,
                has_license = $28, license = $29, published_at = $30,
                quality_score = $31, remixability_score = $32, applicability_score = $33,
                underground_score = $34, hype_risk_score = $35, popularity_score = $36,
                embedding = COALESCE($37::vector, embedding),
                last_crawled_at = now(), updated_at = now()
            WHERE id = $1::uuid
            """,
            str(existing["id"]),
            *update_vals,
        )
        return "updated"

    slug = artifact["slug"]
    try:
        row = await conn.fetchrow(
            f"""
            INSERT INTO artifacts (
                {", ".join(columns)}
            ) VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16::jsonb,$17::jsonb,
                $18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,
                $31,$32,$33,$34,$35,$36,$37::vector
            )
            RETURNING id
            """,
            *values,
        )
    except asyncpg.UniqueViolationError as exc:
        if "artifacts_slug_key" not in str(exc):
            raise
        slug = _unique_slug(slug, canonical)
        values_list = list(values)
        values_list[1] = slug
        row = await conn.fetchrow(
            f"""
            INSERT INTO artifacts (
                {", ".join(columns)}
            ) VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16::jsonb,$17::jsonb,
                $18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,
                $31,$32,$33,$34,$35,$36,$37::vector
            )
            RETURNING id
            """,
            *values_list,
        )

    if row and source_metadata is not None:
        await conn.execute(
            """
            INSERT INTO artifact_sources (artifact_id, source_name, source_url, metadata)
            VALUES ($1::uuid, 'github', $2, $3::jsonb)
            """,
            str(row["id"]),
            artifact["source_url"],
            json.dumps(source_metadata),
        )
    return "inserted"


async def start_crawl_run(conn: asyncpg.Connection, query: str) -> str:
    return str(
        await conn.fetchval(
            """
            INSERT INTO crawl_runs (source_type, query, status)
            VALUES ('github', $1, 'running')
            RETURNING id
            """,
            query,
        )
    )


async def finish_crawl_run(
    conn: asyncpg.Connection,
    run_id: str,
    *,
    status: str,
    artifacts_found: int,
    artifacts_inserted: int,
    artifacts_updated: int = 0,
    error: str | None = None,
) -> None:
    await conn.execute(
        """
        UPDATE crawl_runs
        SET status = $2,
            artifacts_found = $3,
            artifacts_inserted = $4,
            error = $5,
            finished_at = now()
        WHERE id = $1::uuid
        """,
        run_id,
        status,
        artifacts_found,
        artifacts_inserted + artifacts_updated,
        error,
    )
