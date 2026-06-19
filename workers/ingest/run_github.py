#!/usr/bin/env python3
"""GitHub crawler: search vibe-coder repos and ingest as BuildArtifacts.

Safe behavior:
- Dedupes by canonical_url (in-run set + DB upsert)
- Handles rate limits with backoff
- Skips missing READMEs gracefully
- Logs per-query crawl_runs and per-repo outcomes
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKERS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKERS_ROOT))

from dotenv import load_dotenv

load_dotenv(WORKERS_ROOT.parent / ".env")

from common.db import (  # noqa: E402
    finish_crawl_run,
    get_pool,
    start_crawl_run,
    upsert_artifact,
)
from common.cursor import rotate, window_size  # noqa: E402
from common.github import repo_to_artifact  # noqa: E402
from common.github_client import GitHubClient, GitHubRateLimitError  # noqa: E402
from common.paths import API_ROOT  # noqa: E402
from common.relevance import embed_query, heuristic_quality_ok, relevance_ok  # noqa: E402
from common.topics import GITHUB_QUERIES  # noqa: E402

sys.path.insert(0, str(API_ROOT))
from app.utils.urls import canonicalize_url  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("github_crawler")

# Starter vibe-coder discovery terms (user-specified).
STARTER_QUERIES: list[str] = [
    "AI hackathon project",
    "Next.js AI app",
    "full stack AI app",
    "RAG Next.js Supabase",
    "LangChain Next.js",
    "LlamaIndex app",
    "AI agent project",
    "multimodal AI app",
    "voice agent project",
    "video summarizer",
    "lecture summarizer",
    "research paper summarizer",
    "Chrome extension AI",
    "AI flashcard app",
    "computer vision hackathon",
    "Whisper transcription app",
    "AI resume builder",
    "AI code review",
    "MCP server",
    "Claude Code skill",
    "Cursor rules",
]

# GitHub search qualifiers: recent + real-but-underground (min signal, not mega-hyped).
_RECENT_SINCE = (datetime.now(timezone.utc) - timedelta(days=420)).strftime("%Y-%m-%d")
QUALIFIERS = f"pushed:>{_RECENT_SINCE} stars:3..8000"

# Skip repos with effectively no signal before we pay for a README fetch.
MIN_PREFILTER_STARS = int(os.getenv("CRAWL_GITHUB_MIN_STARS", "3"))


def build_search_query(term: str) -> str:
    """Wrap term in quotes and add discovery qualifiers."""
    term = term.strip()
    if term.startswith('"'):
        return f"{term} {QUALIFIERS}"
    return f'"{term}" {QUALIFIERS}'


def _prefilter_repo(repo: dict) -> bool:
    """Cheap gate before the expensive README fetch + embedding."""
    if repo.get("archived") or repo.get("disabled"):
        return False
    if repo.get("fork"):
        return False
    stars = int(repo.get("stargazers_count") or 0)
    has_desc = bool((repo.get("description") or "").strip())
    if stars < MIN_PREFILTER_STARS and not has_desc:
        return False
    return True


@dataclass
class CrawlStats:
    queries_run: int = 0
    repos_seen: int = 0
    repos_skipped_dup: int = 0
    inserted: int = 0
    updated: int = 0
    errors: int = 0
    readme_missing: int = 0
    skipped_irrelevant: int = 0
    seen_canonical: set[str] = field(default_factory=set)


async def process_repo(
    gh: GitHubClient,
    conn,
    repo: dict,
    stats: CrawlStats,
    *,
    dry_run: bool,
    query_embedding=None,
) -> None:
    full_name = repo.get("full_name")
    if not full_name:
        return

    canonical = canonicalize_url(repo.get("html_url", f"https://github.com/{full_name}"))
    if not canonical:
        return

    if canonical in stats.seen_canonical:
        stats.repos_skipped_dup += 1
        logger.debug("Skip duplicate in run: %s", full_name)
        return
    stats.seen_canonical.add(canonical)

    # Cheap gate before paying for the README fetch + embedding.
    if not _prefilter_repo(repo):
        stats.skipped_irrelevant += 1
        return

    try:
        readme = await gh.fetch_readme(full_name)
        if not readme:
            stats.readme_missing += 1

        artifact = repo_to_artifact(repo, readme)
        artifact["canonical_url"] = canonical

        # Quality + semantic relevance gate: keep the index on-topic.
        if not heuristic_quality_ok(artifact):
            stats.skipped_irrelevant += 1
            return
        ok, score = relevance_ok(artifact, query_embedding)
        if not ok:
            stats.skipped_irrelevant += 1
            logger.debug("Skip off-topic %s (rel=%.3f)", full_name, score)
            return

        if dry_run:
            logger.info(
                "[dry-run] %s type=%s quality=%.0f remix=%.0f rel=%.2f",
                full_name,
                artifact["artifact_type"],
                artifact.get("quality_score", 0),
                artifact.get("remixability_score", 0),
                score,
            )
            return

        meta = {
            "github_id": repo.get("id"),
            "stars": repo.get("stargazers_count"),
            "forks": repo.get("forks_count"),
            "topics": repo.get("topics", []),
        }
        result = await upsert_artifact(conn, artifact, source_metadata=meta)
        if result == "inserted":
            stats.inserted += 1
            logger.info("Inserted %s (%s)", full_name, artifact["artifact_type"])
        elif result == "updated":
            stats.updated += 1
            logger.info("Updated %s", full_name)
        else:
            logger.warning("Skipped %s", full_name)
    except Exception as exc:  # noqa: BLE001
        stats.errors += 1
        logger.error("Failed %s: %s", full_name, exc)


async def run_search_query(
    pool,
    gh: GitHubClient,
    term: str,
    stats: CrawlStats,
    *,
    per_page: int,
    max_pages: int,
    dry_run: bool,
) -> None:
    query = build_search_query(term)
    logger.info("=== Search: %s ===", query)

    # Embed the bare term once; reused to gate every candidate in this query.
    query_embedding = embed_query(term.strip().strip('"'))

    async with pool.acquire() as conn:
        run_id = await start_crawl_run(conn, query)
        found = 0
        inserted = 0
        updated = 0
        query_errors = 0

        try:
            for page in range(1, max_pages + 1):
                try:
                    items, total = await gh.search_repositories(
                        query, per_page=per_page, page=page
                    )
                except GitHubRateLimitError as exc:
                    logger.error("Rate limit exhausted for query: %s", exc)
                    break
                except Exception as exc:  # noqa: BLE001
                    logger.error("Search failed page %s: %s", page, exc)
                    query_errors += 1
                    break

                if not items:
                    logger.info("No results on page %s (total=%s)", page, total)
                    break

                logger.info("Page %s: %s repos (total matching ~%s)", page, len(items), total)
                for repo in items:
                    found += 1
                    stats.repos_seen += 1
                    before_ins = stats.inserted
                    before_upd = stats.updated
                    await process_repo(
                        gh, conn, repo, stats, dry_run=dry_run, query_embedding=query_embedding
                    )
                    if stats.inserted > before_ins:
                        inserted += 1
                    if stats.updated > before_upd:
                        updated += 1

                if len(items) < per_page:
                    break
                # Gentle pause between pages.
                await asyncio.sleep(1.0)

            status = "error" if query_errors and found == 0 else "done"
            if not dry_run:
                await finish_crawl_run(
                    conn,
                    run_id,
                    status=status,
                    artifacts_found=found,
                    artifacts_inserted=inserted,
                    artifacts_updated=updated,
                    error="search errors" if query_errors else None,
                )
            logger.info(
                "Query done: found=%s inserted=%s updated=%s errors=%s",
                found,
                inserted,
                updated,
                query_errors,
            )
        except Exception as exc:  # noqa: BLE001
            if not dry_run:
                await finish_crawl_run(
                    conn,
                    run_id,
                    status="error",
                    artifacts_found=found,
                    artifacts_inserted=inserted,
                    artifacts_updated=updated,
                    error=str(exc)[:500],
                )
            raise

    stats.queries_run += 1


async def main_async(args: argparse.Namespace) -> None:
    token = os.getenv("GITHUB_TOKEN") or None
    if not token:
        logger.warning(
            "GITHUB_TOKEN not set — unauthenticated limit is ~10 search requests/hour."
        )
    else:
        logger.info("Using GITHUB_TOKEN for authenticated GitHub API access.")

    if args.query:
        queries = [args.query]
    elif args.limit_queries:
        queries = STARTER_QUERIES[: args.limit_queries]
    else:
        # Rotate a window across the full query set so each run covers new ground.
        queries = rotate("github", GITHUB_QUERIES, window_size("GITHUB_WINDOW", 6))

    stats = CrawlStats()
    pool = await get_pool()

    async with GitHubClient(token=token) as gh:
        for term in queries:
            try:
                await run_search_query(
                    pool,
                    gh,
                    term,
                    stats,
                    per_page=args.per_page,
                    max_pages=args.max_pages,
                    dry_run=args.dry_run,
                )
            except Exception as exc:  # noqa: BLE001
                stats.errors += 1
                logger.exception("Query failed for %r: %s", term, exc)
            if not args.query:
                await asyncio.sleep(2.0)

    await pool.close()

    logger.info("=" * 50)
    logger.info("Crawl summary")
    logger.info("  queries_run:        %s", stats.queries_run)
    logger.info("  repos_seen:         %s", stats.repos_seen)
    logger.info("  skipped_dup_in_run: %s", stats.repos_skipped_dup)
    logger.info("  inserted:           %s", stats.inserted)
    logger.info("  updated:            %s", stats.updated)
    logger.info("  skipped_irrelevant: %s", stats.skipped_irrelevant)
    logger.info("  readme_missing:     %s", stats.readme_missing)
    logger.info("  errors:             %s", stats.errors)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Radar GitHub crawler")
    p.add_argument("--query", help="Run a single starter term instead of the full list")
    p.add_argument("--per-page", type=int, default=30, help="Results per search page")
    p.add_argument("--max-pages", type=int, default=1, help="Pages per query")
    p.add_argument("--limit-queries", type=int, default=0, help="Cap number of starter queries")
    p.add_argument("--dry-run", action="store_true", help="Fetch and map but do not write DB")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
