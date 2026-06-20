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

- **Hybrid search** (full-text + vector) tuned by a built-in eval harness, so only ranking changes that measurably improve quality ship.
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

**4. Search quality you can measure.**
A fast stage casts a wide net (full-text + vector similarity) and fuses the candidates, then metadata scoring orders them. A built-in eval harness scores every ranking change on nDCG@10, MRR, recall, and MAP with a paired significance test, so the pipeline only ships changes that actually help. The optional cross-encoder reranking stage is wired in and stays behind that eval gate.

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

Trove uses **hybrid retrieval, a tuned blend, and a learned reranker**, every stage validated by an eval harness:

1. **Understand the query.** A lightweight rule-based layer pulls out frameworks, tools, and goals (no LLM).
2. **Recall.** Postgres full-text search (field-weighted) and `pgvector` cosine similarity (over local embeddings, with a raised HNSW `ef_search`) pull ~100 candidates per leg and fuse them with weighted Reciprocal Rank Fusion. The fusion weights are tuned, not guessed.
3. **Score.** A metadata blend (relevance, remixability, quality, recency, underground value, substance, minus hype) gates and orders candidates. The weights were fit by random search under nested cross-validation.
4. **Learned rerank (LambdaMART).** A LightGBM listwise model reorders the gated candidates using the same signals as features. It is trained and nested-CV validated by `scripts/train_ltr.py`, scores in microseconds with no model download, and falls back to the linear blend if unavailable. A cross-encoder stage is also wired in but stays eval-gated off (a general-domain model lost to the baseline here).
5. **Explain it.** Every result includes why it is relevant and how to start; every query gets a confidence score and a one-click sharper-query suggestion.

Quality is measured by an **eval harness** (`apps/api/scripts/eval_search.py`) over 50 queries with a ranker-independent relevant set (graded across the whole corpus, so it can see retrieval misses). It reports nDCG@10, MRR, recall@10 and MAP with a paired significance test and bootstrap confidence intervals (via `ranx`), plus a retrieval-vs-ranking diagnostic. Tuning the fusion weights, blend, and gates lifted held-out nDCG@10 from 0.46 to 0.56 (nested CV), and the learned reranker adds a further validated gain on top. The harness gates every ranking change: it ships only if it beats the baseline on queries it was not tuned on.

## The self-improving loop

Trove gets better the more it is used, without manual labeling:

1. **Capture.** Every search logs an impression (which results, at which ranks); clicks and stars log which result the user chose, tied to the query (`search_events`).
2. **Harvest.** `scripts/harvest_eval.py` turns that log into new eval queries (coverage) and `(query, relevant-doc)` training pairs, with **position-bias correction** (clicks are inverse-propensity weighted, since a top-rank click is partly just position).
3. **Retrain.** `scripts/refresh_models.py` retrains the LambdaMART reranker on curated plus harvested data and real click/star labels, then **validates on the frozen curated eval set and rolls back on any regression**. With enough pairs, `scripts/finetune_embeddings.py` fine-tunes the embedding model itself (MNRL + hard-negative mining with false-negative filtering) to lift retrieval recall.
4. **Guardrail.** The hand-written eval set stays frozen and is never trained on, so the loop can grow coverage but can never quietly make quality worse.

Schedule `refresh_models.py` via cron (see `workers/crontab.example`) and the catalog and the ranking both keep improving on their own.

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
| Hybrid retrieval: field-weighted FTS + pgvector + tuned RRF + metadata blend | Done |
| Learned LambdaMART reranker (LightGBM), nested-CV validated, no download | Done |
| Tuning harness: random search under nested cross-validation | Done |
| Eval harness: oracle qrels, nDCG@10/MRR/recall@10/MAP, significance + bootstrap CIs | Done |
| Eval-gated cross-encoder + PRF + MMR (off until they beat baseline) | Done |
| Self-improving loop: usage capture, harvest, retrain, held-out guardrail | Done |
| Embedding fine-tuning from click pairs (MNRL + hard negatives), data-gated | Done |
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
