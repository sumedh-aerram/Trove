<div align="center">

# Trove

### Describe what you're building. See the landscape of what to remix.

Trove is a discovery engine for builders. You type what you are trying to make, and instead of a flat list of links you get an **interactive map of real open-source projects, techniques, starter templates, MCP servers, and papers** you can actually reuse, ranked by how easy they are to remix into *your* project (not by how loud they trend).

It is also a **data layer for AI coding agents**: the same search powers an MCP server, so agents in Cursor, Claude Code, or Cline can pull reusable builds on demand.

</div>

---

## In one line

A live, always-growing catalog of buildable open-source work, with a search that understands what you are making and shows you the best things to fork.

**Highlights**

- **Two-stage search** that finds candidates fast, then reranks the top ones with an AI model for accuracy.
- **A map, not a list:** results render as a graph clustered by theme, closest to the center is the best match.
- **Live crawlers** for GitHub, Hacker News, and arXiv run 24/7 in the background, so the index keeps growing on its own.
- **Agent ready:** an MCP server lets coding agents query the exact same search.
- **Instant and free:** search reads a database in milliseconds and makes zero paid LLM calls.

---

## The problem

When you start something new, the hardest part usually isn't writing code. It's finding the 70% that already exists.

Say you want to build an AI lecture summarizer with quizzes. Someone has already solved the transcription, the chunking, the quiz prompt, the auth, the billing. But finding their work means:

- digging through GitHub stars (where "popular" usually means old and huge, not useful to you),
- doomscrolling Hacker News and Twitter,
- skimming arXiv,
- and reading a hundred "Top 10 AI repos" posts that all list the same five hyped libraries.

AI made this worse. Everyone ships now, so the registries are flooded. Normal search ranks by popularity and SEO. What a builder actually needs is ranking by **remixability**: can I pull this into my project this weekend? Those are different questions, and nothing answers the second one.

**Trove answers the second one**, and it shows how the options relate, so you can pick a direction in 30 seconds instead of 3 hours of open tabs.

## What it feels like

Type a real, messy query like:

> *"a RAG chrome extension that explains research papers, TypeScript preferred"*

Trove gives you a **landscape**, not a list:

- a node graph with your query in the center and matches around it. **Closer means more relevant.** Matches are grouped into themes (Projects, Templates, Agent/MCP tooling, Research, Libraries).
- a **match-confidence score** for your query. If your query is vague, it says so and **suggests a sharper query you can run with one click**.
- for any result: **why it fits you**, what it **is**, **how it helps**, **why it stands out**, the exact **commands to start**, and the tech stack.

It indexes far more than repos: starter templates, techniques, MCP servers, coding-agent workflows, architecture patterns, and papers.

## Why it's different

**1. Ranked for remixability, not popularity.**
Each result gets a blended score from relevance to your project, remixability, quality, and recency, minus a hype-risk penalty. An "underground" score even surfaces strong projects before they go viral. You get things you can use, not things that are just trending.

**2. A map, not a list.**
Results render as an interactive graph so you can see structure at a glance: which options are closest to your intent, how they cluster, and which are the strongest matches.

**3. The index is live and always growing.**
Background crawlers for GitHub, Hacker News, and arXiv run continuously, 24/7, with no manual work. New builds get scored, embedded, and added on their own, and the home page shows the index growing in real time ("+N added today", "last new just now"). Crawling runs separately from search, so the catalog stays fresh without ever slowing a query down.

**4. Two-stage search for accuracy.**
First a fast stage casts a wide net (full-text + vector similarity). Then a smarter AI model (a cross-encoder) re-reads the top candidates against your query and reorders them so the best result lands first. This "retrieve then rerank" approach is how modern search and RAG systems work.

**5. It speaks fluent agent, with no paid LLM tax.**
A first-class MCP server gives AI coding agents the exact same search through clean structured data. Trove makes zero paid LLM calls for discovery. It is the curated index agents query, not another wrapper around web search.

## Who it's for

- **Vibe coders and indie hackers** who want a forkable head start instead of a blank repo.
- **Hackathon teams** who need to ship a demo this weekend.
- **AI coding agents** (via MCP) that need a queryable index of reusable builds.

## How it works

```
   LIVE crawlers (24/7)            relevance + quality gate          PostgreSQL
GitHub ─▶  a saved cursor rotates ─▶  embed + check it matches  ─▶   + pgvector
HN ─────▶  through all topics so      the topic, drop the noise      UPSERT by URL
arXiv ──▶  every run finds new        ↓                              (no duplicates)
                                      scores + embedding are computed
                                      AT INGEST, never at query time
                                                                       │
                  Next.js web  ◀─┐                                     │
                                 ├── GET /search  (read only, no crawl) ◀┘
                  MCP server  ◀──┘   full-text + vector + rerank
                  (coding agents)
```

**The rule that makes it fast:** the writers (crawlers) and the readers (web app, MCP) are fully separate. Heavy work happens once, when data is ingested. Reads are cheap, identical across both surfaces, and instant.

## The search pipeline

Trove uses **two-stage retrieval (retrieve, then rerank)**:

1. **Understand the query.** A lightweight rule-based layer pulls out frameworks, tools, and goals (no LLM).
2. **Stage 1, recall.** Postgres full-text search and `pgvector` cosine similarity (over local embeddings) pull ~60 candidates and fuse them with Reciprocal Rank Fusion. Fast, and it rarely misses anything.
3. **Metadata ranking.** Candidates are scored on relevance, remixability, quality, recency, and underground value, minus hype risk.
4. **Stage 2, precision.** A cross-encoder reranker (`ms-marco-MiniLM-L-6`) re-reads the top candidates against the query and reorders them, then blends into the final ranking.
5. **Explain it.** Every result includes why it is relevant and how to start; every query gets a confidence score and a one-click sharper-query suggestion.

Quality is measured by an **eval harness** (`apps/api/scripts/eval_search.py`) that reports recall@k, MRR, and nDCG@10. Stage-2 reranking improves nDCG@10 over stage 1 alone. Stage 1 returns in tens of milliseconds, and the reranker only touches the top results, so warm searches stay well under a second.

## Quick start

```bash
cp .env.example .env          # optional: add a GITHUB_TOKEN for faster, fuller GitHub crawls
docker compose up -d          # starts Postgres + pgvector AND the always-on background crawler
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
npm run dev                   # open http://localhost:3000
```

That's it. The index fills itself: the moment the crawler starts it pulls from Hacker News, GitHub, and arXiv, then keeps adding new builds on a short interval. The home page shows the live count, how many were added today, and when the last new build landed, so you can literally watch it grow.

> Want a big index instantly on a fresh clone? Let it crawl for a while, then run
> `python packages/db/export_seed_from_db.py` and commit `packages/db/seed.sql`.

## Connect a coding agent (MCP)

```bash
cd apps/mcp && npm install && npm run build
```

```json
{
  "mcpServers": {
    "trove": {
      "command": "node",
      "args": ["/absolute/path/to/Trove/apps/mcp/dist/index.js"],
      "env": { "API_BASE_URL": "http://localhost:8000" }
    }
  }
}
```

Then ask your agent: *"Use Trove to find open-source repos for a RAG Chrome extension over research papers."* Tools: `search_artifacts`, `find_similar_projects`, `get_artifact_details`, `recommend_stack`. Full docs: **[apps/mcp/README.md](apps/mcp/README.md)**.

## Live crawling, in detail

The Docker `crawler` service runs continuously (`restart: unless-stopped`), so it survives restarts and needs nothing launched by hand. It is capped on CPU and memory so it never overwhelms your machine. Three things keep it adding genuinely new builds instead of re-scanning the same ones:

- **Topic rotation.** A saved cursor advances every run, so successive crawls sweep the whole topic list (dozens of builder topics) rather than re-hitting the first few.
- **A "newest" feed.** Hacker News is pulled both by relevance and by date, so fresh posts keep flowing in.
- **Honest accounting.** Each run reports `new` vs `refreshed` separately, and the app shows real new additions (not re-touches).

Run any job by hand too:

```bash
cd workers
python run_scheduled.py hn        # Hacker News (top + newest)
python run_scheduled.py github    # GitHub repos (set GITHUB_TOKEN for speed)
python run_scheduled.py arxiv     # arXiv papers (newest first)
python run_scheduled.py embeddings
```

Default cadence: Hacker News every ~5 min, GitHub every ~20 min, arXiv every ~3 h. Search **never** triggers a crawl.

## Monorepo layout

```
apps/web/      Next.js 15 frontend: animated home, interactive landscape graph, detail pages
apps/api/      FastAPI backend: two-stage search, ranking, reranking, confidence, stats
apps/mcp/      TypeScript MCP server: calls the API, no database, no LLM
workers/       Live crawlers (GitHub, HN, arXiv) + rotation cursor + daemon + embedding backfill
packages/db/   PostgreSQL + pgvector schema, seed, and a DB-to-seed exporter
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/search?q=` | Two-stage search: ranked results, clusters, confidence, suggestion |
| GET | `/artifacts`, `/artifacts/{id}` | List, filter, detail |
| POST/DELETE | `/artifacts/{id}/star` | Save / unsave |
| GET | `/stats` | Index size, embeddings %, builds added today, crawl freshness |
| GET | `/profiles/{username}`, `/leaderboard` | Profiles |

## Tech stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js 15, TypeScript, Tailwind |
| Backend | FastAPI, asyncpg |
| Data | PostgreSQL + pgvector (full-text + HNSW vector index) |
| Embeddings | SentenceTransformers `all-MiniLM-L6-v2` (local, no paid LLM) |
| Reranker | Cross-encoder `ms-marco-MiniLM-L-6-v2` (local) |
| Agent layer | Model Context Protocol (TypeScript) |
| Crawlers | Python (GitHub REST, HN Algolia, arXiv API) |

## Status

| Capability | State |
|------------|-------|
| Two-stage retrieval: full-text + pgvector + RRF, then cross-encoder reranking | Done |
| Eval harness (recall@k, MRR, nDCG@10) | Done |
| Live, always-on crawler daemon (GitHub, HN, arXiv) with rotation | Done |
| Interactive relevance-graph UI | Done |
| Query match-confidence + one-click sharper-query suggestion | Done |
| Per-result why-relevant / about / how-it-helps / stands-out / how-to-start | Done |
| Remixability / quality / hype-risk / underground scoring | Done |
| MCP server (search, similar, details, recommend-stack) | Done |
| Hugging Face / RSS crawlers | Planned |
| Hosted deployment and real auth | Planned |

## Where it goes next

- One-command hosted deploy (managed Postgres + API) so a whole team shares one fresh index.
- Hugging Face and RSS crawlers for models and builder blogs.
- Search analytics from real queries to keep tuning ranking.

## License

MIT, see [LICENSE](LICENSE).
