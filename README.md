# Build Radar

**Uiverse for full-stack builders** — discover open-source projects, techniques, starter templates, MCP servers, and coding-agent workflows you can remix into what you're building.

> Uiverse = copy-paste UI components.  
> Build Radar = copy-paste project ideas, repos, techniques, and workflows.

## Monorepo layout

```
apps/web/     Next.js 15 frontend
apps/api/     FastAPI backend
apps/mcp/     TypeScript MCP server (calls API, no DB logic)
workers/      Python crawlers + embedding backfill
packages/db/  PostgreSQL schema + seed data
```

## Prerequisites

- Docker (Postgres + pgvector)
- Node.js 20+
- Python 3.11+ (3.12 recommended)

## Quick start (local)

### 1. Environment

```bash
cp .env.example .env
# Optional: set GITHUB_TOKEN for crawlers
```

### 2. Database + background crawler

```bash
docker compose up -d
# Postgres: schema + seed on first boot (small starter set).
# crawler: bootstraps a larger index when count < 40, then refreshes HN/GitHub/arXiv on a schedule.
# Set GITHUB_TOKEN in .env for faster, fuller GitHub indexing.
```

Postgres is on host port **5433**. Search stays **instant** (reads Postgres only). New artifacts appear after background crawls finish — refresh search or wait for the status bar count to rise.

**Grow the seed for new clones:** after crawling, run `python packages/db/export_seed_from_db.py` and commit `packages/db/seed.sql`. See [packages/db/README.md](packages/db/README.md) (current seed = **12** artifacts).

Re-apply manually if needed:

```bash
docker exec -i build_radar_pg psql -U postgres -d build_radar < packages/db/schema.sql
docker exec -i build_radar_pg psql -U postgres -d build_radar < packages/db/seed.sql
```

### 3. API

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 4. Embeddings (optional if crawler is running)

The `crawler` service and `bootstrap_index.py` run `backfill_embeddings` automatically. Manual:

```bash
cd workers && python ingest/backfill_embeddings.py
```

### 5. Frontend

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000

**Try the UI:** search from the home bar → results with artifact cards → click **Details** → **Star** on cards or detail page.

Copy `apps/web/.env.local.example` → `apps/web/.env.local` if the API is not on port 8000.

### 6. GitHub crawler (optional)

```bash
cd workers
pip install -r requirements.txt
# Set GITHUB_TOKEN in .env for higher rate limits
python ingest/run_github.py

# Single query dry-run:
python ingest/run_github.py --dry-run --query "MCP server"
```

Searches 21 vibe-coder starter terms, fetches READMEs, extracts stack metadata,
scores artifacts, generates embeddings, dedupes by `canonical_url`, and logs `crawl_runs`.

**Scheduled crawls (cron-ready):**

```bash
cd workers
python run_scheduled.py --list
python run_scheduled.py github    # every 30–60m recommended
python run_scheduled.py hn        # every 15–30m
python run_scheduled.py arxiv     # every 6–12h
python run_scheduled.py embeddings
```

See `workers/crontab.example` for sample cron entries.

### 7. MCP server (for coding agents)

```bash
cd apps/mcp
npm install
npm run build
API_BASE_URL=http://localhost:8000 npm start
```

Full setup, client config (Cursor / Claude / Cline), and example tool I/O: **[apps/mcp/README.md](apps/mcp/README.md)**.

## Smoke tests

With API running:

```bash
chmod +x scripts/smoke_test.sh scripts/search_quality_test.sh
./scripts/smoke_test.sh
./scripts/search_quality_test.sh   # asserts lecture/RAG/MCP/CV queries
```

Pytest (from `apps/api`):

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/build_radar \
  PYTHONPATH=. pytest tests/test_search_unit.py tests/test_search_integration.py -q
```

Or manual curls:

```bash
curl "http://localhost:8000/health"
curl -G "http://localhost:8000/search" --data-urlencode "q=AI lecture summarizer"
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/artifacts` | List/filter artifacts |
| GET | `/artifacts/{id}` | Artifact detail |
| GET | `/search?q=` | Hybrid search |
| POST/DELETE | `/artifacts/{id}/star` | Star/unstar |
| GET | `/profiles/{username}` | Profile + star count |
| GET | `/leaderboard` | Top profiles |

## Search architecture

1. Rule-based **project intent** extraction (frameworks, tools, tags)
2. **Full-text** search (Postgres `tsvector`)
3. **Vector** search (pgvector cosine, SentenceTransformers `all-MiniLM-L6-v2`)
4. **RRF** fusion + metadata-weighted final score
5. `why_relevant` string per result

No paid LLM calls for search.

## Cost rule

Artifacts are **pre-indexed**. Search hits your database. The MCP server returns structured JSON; the user's coding agent does expensive reasoning on their own subscription.

## What's implemented vs stubbed

| Feature | Status |
|---------|--------|
| Schema + seed (12 artifacts) | ✅ |
| FastAPI CRUD + search + stars | ✅ |
| Hybrid FTS + vector search | ✅ (needs embedding backfill) |
| Rule-based scoring + moderation | ✅ |
| Next.js pages (home, search, detail, profile) | ✅ |
| GitHub crawler | ✅ |
| HN + arXiv crawlers | ✅ |
| MCP server (4 tools) | ✅ |
| Hugging Face crawler | 🔲 stub |
| RSS crawler | 🔲 stub |
| Real auth | 🔲 fake username only |
| Admin moderation UI | 🔲 API only via `user_posts.status` |

## Suggested next builds

1. Admin moderation endpoints + pending queue UI
2. Hugging Face + RSS crawlers
3. Supabase deployment + real auth (Clerk/Supabase)
4. Search analytics dashboard from `search_events`
5. Live scan fallback when DB has no matches

## License

MIT (add your own LICENSE file when you open-source the repo)
