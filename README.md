<div align="center">

# Build Radar

### Describe what you're building. See the landscape of what to remix.

Build Radar is a discovery engine for builders. You type what you're trying to make, and instead of a flat list of links it gives you an **interactive map of the real open-source projects, techniques, starter templates, MCP servers, and papers** you can actually reuse — ranked by how remixable they are for *your* project, not by how loud they trend.

It's also the missing **data layer for coding agents**: the same search powers an MCP server, so agents in Cursor / Claude Code / Cline can pull remixable builds on demand.

</div>

---

## The problem

Starting something new, the hardest part usually isn't writing code — it's finding the 70% that already exists.

You want to build, say, an AI lecture summarizer with quizzes. Someone has already solved the transcription, the chunking, the quiz prompt, the auth, the billing. But finding their work means:

- crawling GitHub stars (where "popular" means *old and huge*, not *useful to you*),
- doomscrolling Hacker News and Twitter,
- skimming arXiv,
- and reading a hundred "Top 10 AI repos" posts that all list the same five hyped libraries.

Then AI made it *worse*: everyone ships now, so the registries are flooded. General search ranks by **popularity and SEO**. What a builder actually needs is ranking by **remixability** — *can I pull this into my project this weekend?* Those are different questions, and nothing answers the second one.

**Build Radar answers the second one** — and shows you how the options relate, so you can pick a direction in 30 seconds instead of 3 hours of tabs.

## The "aha"

Type a real, messy, project-context query:

> *"a RAG chrome extension that explains research papers, TypeScript preferred"*

Build Radar returns a **landscape**, not a list:

- a node graph with your query at the center and matches orbiting it — **closer = more relevant**, clustered into themes (Projects, Templates, Agent/MCP tooling, Research, Libraries);
- a **match-confidence score** for your query — if it's vague, it tells you and **suggests a sharper query you can run in one click**;
- for any result: **why it's relevant to you**, what it's **about**, **how it helps**, **why it stands out**, the exact **how-to-start** commands, and the stack.

It indexes far more than repos — **starter templates, techniques, MCP servers, coding-agent workflows, architecture patterns, and papers** — the full surface of how things actually get built.

## Why it's different

**1. Ranked for remixability, not popularity.**
A blended score — relevance to your project, remixability, quality, recency, *minus* a hype-risk penalty — plus an `underground` score that surfaces high-signal projects *before* they hit the front page. You get things you can use, not things that are merely viral.

**2. A map, not a list.**
Results render as an interactive relevance graph so you can see structure — which options are close to your intent, how they cluster, what the strongest matches are — instead of scrolling ten blue links.

**3. Search is instant because crawling never touches it.**
Everything is pre-indexed. Embeddings and scores are computed at **ingestion**. A query is pure Postgres — full-text (`tsvector`) + vector (`pgvector` cosine) fused with Reciprocal Rank Fusion — returning in milliseconds. Crawlers run continuously in the **background** and never block a user. Freshness without latency.

**4. It speaks fluent agent.**
A first-class **MCP server** exposes the *exact same* search API to coding agents. The agent gets clean structured JSON (titles, scores, remix notes, setup steps) and reasons on *its own* model. Build Radar makes **zero paid LLM calls** for discovery — it's the curated index agents query, not another wrapper around web search.

**5. Project-context understanding, no LLM tax.**
A rule-based intent layer pulls frameworks, tools, and goals from your sentence and enriches retrieval — so a "lecture summarizer with quizzes in Next.js + Supabase" finds the right starter even when those exact words aren't in its README.

## Who it's for

- **Vibe coders / indie hackers** starting a project who want a forkable head start, not a blank repo.
- **Hackathon teams** who need to ship a demo this weekend.
- **Coding agents** (via MCP) that need a queryable index of remixable builds.

## How it works

```
        rotating topic lists           relevance + quality gate          PostgreSQL
GitHub ─▶  (a saved cursor sweeps  ─▶   embed → cosine vs topic     ─▶   + pgvector
HN ─────▶   the full topic set so       + heuristics (drop noise)        UPSERT by
arXiv ──▶    each run finds new)         ↓                                canonical_url
                                         scores + embedding computed
                                         AT INGEST (never at query time)
                                                                          │
                  Next.js web  ◀─┐                                        │
                                 ├── GET /search  (reads only, no crawl) ◀┘
                  MCP server  ◀──┘   FTS + pgvector + Reciprocal Rank Fusion
                  (coding agents)
```

**The rule that makes it fast:** writers (crawlers) and readers (web, MCP) are fully decoupled. Heavy work happens once, at ingestion. Reads are cheap, identical across surfaces, and instant.

## The search pipeline

**Two-stage retrieval (retrieve → rerank):**

1. **Project-intent extraction** — frameworks, tools, tags, project type (rule-based, no LLM).
2. **Stage 1 — recall** — Postgres full-text (`ts_rank_cd`) + `pgvector` cosine ANN over local SentenceTransformers (`all-MiniLM-L6-v2`) embeddings, fused with **Reciprocal Rank Fusion**.
3. **Metadata ranking** — relevance · remixability · quality · recency · underground − hype-risk.
4. **Stage 2 — precision** — a **cross-encoder reranker** (`ms-marco-MiniLM-L-6`) rescues the top candidates by reading each (query, doc) pair jointly, then blends into the final order.
5. **Explainability** — per-result `why_relevant`, key points, how-to-start; per-query match confidence + a one-click sharper-query suggestion.

Measured with an **eval harness** (`apps/api/scripts/eval_search.py`) reporting recall@k / MRR / nDCG@10; stage-2 reranking improves nDCG@10 over stage-1 alone. Stage 1 returns in tens of ms; the cross-encoder reranks only the top-K, so warm queries stay well under a second.

## Quick start

```bash
cp .env.example .env          # optional: set GITHUB_TOKEN for fuller, faster GitHub crawls
docker compose up -d          # Postgres + pgvector, plus the always-on background crawler
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

The index fills itself: the background crawler bootstraps from Hacker News, GitHub, and arXiv, then keeps adding on a short interval. The home page shows live index size, **+N added today**, and when the last new build landed — so you can watch it grow.

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

Then ask your agent: *"Use Build Radar to find open-source repos for a RAG Chrome extension over research papers."* Tools: `search_artifacts`, `find_similar_projects`, `get_artifact_details`, `recommend_stack`. Full docs: **[apps/mcp/README.md](apps/mcp/README.md)**.

## Monorepo layout

```
apps/web/      Next.js 15 frontend — animated home, interactive landscape graph, detail
apps/api/      FastAPI backend — hybrid search, ranking, landscape + confidence, stats
apps/mcp/      TypeScript MCP server — calls the API, no DB, no LLM
workers/       Crawlers (GitHub · HN · arXiv) + rotation cursor + daemon + embedding backfill
packages/db/   PostgreSQL + pgvector schema, seed, and DB→seed exporter
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/search?q=` | Hybrid search → ranked results, clusters, confidence, suggestion |
| GET | `/artifacts` · `/artifacts/{id}` | List / filter / detail |
| POST/DELETE | `/artifacts/{id}/star` | Star / unstar |
| GET | `/stats` | Index size, embeddings %, builds added today, crawl freshness |
| GET | `/profiles/{username}` · `/leaderboard` | Profiles |

## Crawling & freshness

The Docker `crawler` daemon runs continuously (`restart: unless-stopped`) — nothing to launch — and is CPU/RAM-capped so it won't cook the machine. A **rotation cursor** advances each run, so successive crawls sweep the whole topic set instead of re-hitting the same queries, and HN pulls a **newest-stories feed** so it keeps finding genuinely new builds. You can also run jobs by hand:

```bash
cd workers
python run_scheduled.py hn        # Hacker News (top + newest)
python run_scheduled.py github    # repos (set GITHUB_TOKEN for speed)
python run_scheduled.py arxiv     # papers (newest first)
python run_scheduled.py embeddings
```

Default cadence: HN ~5m · GitHub ~20m · arXiv ~3h. Search **never** triggers a crawl.

## Tech stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js 15 · TypeScript · Tailwind |
| Backend | FastAPI · asyncpg |
| Data | PostgreSQL + pgvector (FTS + HNSW) |
| Embeddings | SentenceTransformers `all-MiniLM-L6-v2` (local, no paid LLM) |
| Reranker | Cross-encoder `ms-marco-MiniLM-L-6-v2` (local) |
| Agent layer | Model Context Protocol (TypeScript) |
| Crawlers | Python (GitHub REST · HN Algolia · arXiv API) |

## Status

| Capability | State |
|------------|-------|
| Two-stage retrieval: hybrid FTS + pgvector ANN + RRF, then cross-encoder reranking | ✅ |
| Eval harness (recall@k · MRR · nDCG@10) | ✅ |
| Interactive relevance-graph "landscape" UI | ✅ |
| Query match-confidence + one-click sharper-query suggestion | ✅ |
| Per-result why_relevant / about / how-it-helps / stands-out / how-to-start | ✅ |
| Remixability / quality / hype-risk / underground scoring | ✅ |
| Always-on crawler daemon with rotation + new-vs-refreshed accounting | ✅ |
| MCP server (search, similar, details, recommend-stack) | ✅ |
| Embedding backfill + DB→seed export | ✅ |
| Hugging Face / RSS crawlers | 🔲 stubbed |
| Hosted deployment + real auth | 🔲 next |

## Where it goes next

- One-command hosted deploy (managed Postgres + API) so a whole team shares one fresh index.
- Hugging Face + RSS crawlers for models and builder blogs.
- Search analytics from `search_events` to tune ranking on real queries.
- Optional live-scan fallback when the index has a genuine gap.

## License

MIT — add a `LICENSE` file before open-sourcing.
