<div align="center">

# Build Radar

### The discovery engine for people who actually ship.

**Describe what you're building. Get back the real open-source projects, techniques, starter templates, MCP servers, and agent workflows you can remix — ranked by how remixable they actually are, not how loud they trend.**

</div>

---

## The problem

Every builder loses the same hours.

You have an idea. You know *someone* has already solved 70% of it — the auth flow, the RAG pipeline, the Whisper integration, the agent loop. But finding it means crawling GitHub stars, doomscrolling Hacker News, skimming arXiv, and digging through a hundred "Top 10 AI repos" posts that are all the same five hyped libraries.

Search engines rank by **popularity**. Builders need ranking by **remixability** — *can I actually pull this into my project this weekend?*

Those are not the same question. Build Radar answers the second one.

## What it does

You type a full project-context query — *"I'm building a RAG Chrome extension that explains research papers, TypeScript preferred"* — and Build Radar returns concrete artifacts with:

- **`why_relevant`** — why this matches *your* project, not just your keywords
- **`how_to_remix`** — what to fork, swap, and keep
- **setup commands + implementation steps** — pulled from the source
- **honest scores** — quality, remixability, hype-risk, and an "underground" score that surfaces gems before they're famous

It indexes more than repos: **starter templates, techniques, MCP servers, coding-agent workflows, architecture patterns, and papers** — the full surface area of how things actually get built today.

## Why it's different

**1. It ranks for remixability, not popularity.**
A blended score — project relevance, remixability, quality, recency, *minus* a hype-risk penalty — so you get things you can use, not things that are merely viral. The `underground_score` deliberately surfaces high-signal projects before they hit the front page.

**2. Search is instant because crawling never touches the search path.**
Everything is pre-indexed. Embeddings and scores are computed at ingestion time. A query is pure Postgres — full-text (`tsvector`) + vector (pgvector cosine) fused with Reciprocal Rank Fusion — and returns in milliseconds. Crawlers run continuously in the **background** and never block a user. Freshness without latency.

**3. It speaks fluent agent.**
Build Radar ships a first-class **MCP server**. Your coding agent (Cursor, Claude Code, Cline) calls the *exact same* search API the website uses. The agent gets clean structured JSON — titles, scores, remix notes, setup steps — and does the reasoning on *its own* model subscription. Build Radar runs **zero paid LLM calls** for discovery.

**4. Project-context understanding, no LLM tax.**
A rule-based intent layer extracts frameworks, tools, and goals from your sentence, then enriches retrieval — so "lecture summarizer with quizzes in Next.js + Supabase" finds the right starter even when none of those exact words are in its README.

## How it works

```
                          ┌──────────────────────────────┐
   GitHub · HN · arXiv ──▶│   Background crawlers          │
                          │   normalize → score → embed    │
                          └───────────────┬────────────────┘
                                          │ upsert (dedupe by URL)
                                          ▼
                            ┌──────────────────────────┐
                            │  PostgreSQL + pgvector    │   ◀── single source of truth
                            │  FTS index · HNSW vectors │
                            └─────────────┬─────────────┘
                                          │ reads only (no crawl)
                        ┌─────────────────┴─────────────────┐
                        ▼                                     ▼
                 ┌─────────────┐                      ┌──────────────┐
                 │  FastAPI    │  same /search API    │  MCP server  │
                 │  hybrid     │◀────────────────────▶│  (4 tools)   │
                 │  search     │                      └──────┬───────┘
                 └──────┬──────┘                             │
                        ▼                                     ▼
                 Next.js web app                     Coding agents
                 (search · cards · detail)           (Cursor / Claude / Cline)
```

**The rule that makes it fast:** writers (crawlers) and readers (search, MCP, web) are fully decoupled. Heavy work happens once, at ingestion. Reads are cheap, identical across surfaces, and instant.

## The search pipeline

1. **Project-intent extraction** — frameworks, tools, tags, project type (rule-based, no LLM)
2. **Full-text retrieval** — Postgres `ts_rank_cd` across multiple strategies
3. **Vector retrieval** — pgvector cosine over local SentenceTransformers (`all-MiniLM-L6-v2`) embeddings
4. **Reciprocal Rank Fusion** — merges keyword, vector, and intent signals
5. **Final ranking** — relevance · remixability · quality · recency · underground − hype-risk
6. **`why_relevant`** — a tailored explanation generated per result

## Quick start

```bash
cp .env.example .env          # optional: set GITHUB_TOKEN for fuller GitHub crawls

docker compose up -d          # Postgres + pgvector, plus the background crawler
```

```bash
# API
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
# Web
cd apps/web
npm install
npm run dev                   # http://localhost:3000
```

The index starts empty and fills itself: the background crawler bootstraps from Hacker News, GitHub, and arXiv, then keeps refreshing on a short interval. Search is live the moment the first artifacts land — and stays instant the whole time.

> Want a fat index immediately on a fresh clone? Crawl for a while, then
> `python packages/db/export_seed_from_db.py` and commit `packages/db/seed.sql`.

## Connect a coding agent (MCP)

```bash
cd apps/mcp && npm install && npm run build
```

```json
{
  "mcpServers": {
    "build-radar": {
      "command": "node",
      "args": ["/absolute/path/to/Build Radar/apps/mcp/dist/index.js"],
      "env": { "API_BASE_URL": "http://localhost:8000" }
    }
  }
}
```

Then ask your agent: *"Use Build Radar to find open-source repos for a RAG Chrome extension over research papers."* Full tool docs: **[apps/mcp/README.md](apps/mcp/README.md)**.

## Monorepo layout

```
apps/web/      Next.js 15 frontend (search, cards, detail, stars)
apps/api/      FastAPI backend (hybrid search, scoring, stats)
apps/mcp/      TypeScript MCP server — calls the API, no DB, no LLM
workers/       Crawlers (GitHub · HN · arXiv) + scheduler + embedding backfill
packages/db/   PostgreSQL + pgvector schema, seed, and DB→seed exporter
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/search?q=` | Hybrid project-context search |
| GET | `/artifacts` | List / filter artifacts |
| GET | `/artifacts/{id}` | Artifact detail |
| POST/DELETE | `/artifacts/{id}/star` | Star / unstar |
| GET | `/stats` | Index size, embeddings %, crawl freshness |
| GET | `/profiles/{username}` | Profile + star count |
| GET | `/leaderboard` | Top profiles |

## Crawling & freshness

Crawlers run manually, on cron, via the Docker `crawler` daemon, or as a background refresh after search — **never on the search path itself**.

```bash
cd workers
python run_scheduled.py --list
python run_scheduled.py github       # repos
python run_scheduled.py hn           # Hacker News stories
python run_scheduled.py arxiv        # papers
python run_scheduled.py embeddings   # backfill vectors
```

Recommended cadence (see `workers/crontab.example`): GitHub 30–60m · HN 15–30m · arXiv 6–12h.

## Tech stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js 15 · TypeScript · Tailwind |
| Backend | FastAPI · asyncpg |
| Data | PostgreSQL + pgvector (FTS + HNSW) |
| Embeddings | SentenceTransformers `all-MiniLM-L6-v2` (local, no paid LLM) |
| Agent layer | Model Context Protocol (TypeScript) |
| Crawlers | Python (GitHub REST · HN Algolia · arXiv API) |

## Status

| Capability | State |
|------------|-------|
| Hybrid FTS + vector search with RRF | ✅ |
| Project-intent extraction + `why_relevant` | ✅ |
| Remixability / quality / hype-risk / underground scoring | ✅ |
| Background crawler daemon (GitHub · HN · arXiv) | ✅ |
| MCP server (search, similar, details, recommend-stack) | ✅ |
| Next.js app (home, search, detail, stars) | ✅ |
| Embedding backfill + DB→seed export | ✅ |
| Hugging Face / RSS crawlers | 🔲 stubbed |
| Hosted deployment + real auth | 🔲 next |

## Where it goes next

- One-command hosted deploy (managed Postgres + API) so a whole team shares one fresh index
- Hugging Face + RSS crawlers for models and builder blogs
- Search analytics from `search_events` to tune ranking on real queries
- Optional live-scan fallback when the index has a genuine gap

## License

MIT — add a `LICENSE` file before open-sourcing.
