# Build Radar MCP Server

Connects **coding agents** (Cursor, Claude Code, Cline, etc.) to [Build Radar](https://github.com) via the **FastAPI backend**.

| Design rule | Behavior |
|-------------|----------|
| No Postgres | All data comes from `GET /search`, `GET /artifacts/{id}`, etc. |
| No LLM calls | Tools return structured JSON; **your agent** does the reasoning |
| Project-context search | Pass full “what I’m building” queries, not just keywords |

## Prerequisites

1. **Postgres + seed** running (`docker compose up -d` from repo root)
2. **FastAPI API** on port 8000:

```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

3. Verify: `curl http://localhost:8000/health` → `{"status":"ok"}`

## Install & run locally

```bash
cd apps/mcp
npm install
npm run build
API_BASE_URL=http://localhost:8000 npm start
```

The server uses **stdio** transport (stdin/stdout). Do not print logs to stdout — diagnostics go to stderr.

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `http://localhost:8000` | Build Radar FastAPI base URL |
| `API_TIMEOUT_MS` | `30000` | HTTP timeout per request |

Copy from repo root:

```bash
cp ../../.env.example .env   # optional; export API_BASE_URL manually
```

## Configure a coding-agent client

Use the **absolute path** to `dist/index.js` on your machine.

### Cursor

**Settings → MCP → Add server** (or edit `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "build-radar": {
      "command": "node",
      "args": ["/absolute/path/to/Build Radar/apps/mcp/dist/index.js"],
      "env": {
        "API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

Restart Cursor. In Agent chat, the model can call `search_artifacts`, `find_similar_projects`, etc.

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "build-radar": {
      "command": "node",
      "args": ["/absolute/path/to/Build Radar/apps/mcp/dist/index.js"],
      "env": {
        "API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Claude Code

Add to your MCP config (e.g. `~/.claude/settings.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "build-radar": {
      "type": "stdio",
      "command": "node",
      "args": ["/absolute/path/to/Build Radar/apps/mcp/dist/index.js"],
      "env": {
        "API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Cline / other stdio MCP clients

Same pattern: `command` = `node`, `args` = `[path/to/dist/index.js]`, `env.API_BASE_URL` = your API.

---

## Tools

### 1. `search_artifacts`

Search indexed artifacts using a **project-context** query.

**Input example:**

```json
{
  "query": "I'm building a RAG Chrome extension that explains research papers. I need open-source repos and libraries.",
  "frameworks": ["Next.js", "TypeScript"],
  "limit": 5
}
```

**Output example** (abbreviated):

```json
{
  "results": [
    {
      "id": "00000000-0000-0000-0000-000000000002",
      "title": "paperpal/rag-chrome-extension",
      "source_url": "https://github.com/paperpal/rag-chrome-extension",
      "artifact_type": "starter_template",
      "summary": "Chrome extension boilerplate that explains the current web page or PDF using RAG over its content.",
      "why_relevant": "Matches your project because it combines browser extension architecture with RAG over research papers.",
      "how_to_remix": "Replace the embedding backend with your own API, change the system prompt, and point the retriever at your own document store.",
      "implementation_steps": ["Load the unpacked extension in Chrome", "Configure your model endpoint in options"],
      "setup_commands": ["git clone https://github.com/paperpal/rag-chrome-extension", "npm install", "npm run build"],
      "tags": ["rag", "extension", "browser", "pdf"],
      "frameworks": ["Chrome Extension", "React", "Vite"],
      "tools": ["LangChain", "Chroma"],
      "quality_score": 79,
      "remixability_score": 81,
      "hype_risk_score": 22
    }
  ]
}
```

---

### 2. `find_similar_projects`

Find remixable repos similar to the user’s project.

**Input example:**

```json
{
  "project_description": "AI lecture summarizer with quiz generation using Next.js and Supabase",
  "current_stack": ["Next.js", "Supabase", "Whisper"],
  "desired_features": ["quiz", "flashcards"],
  "limit": 5
}
```

**Output example:**

```json
{
  "results": [
    {
      "id": "00000000-0000-0000-0000-000000000001",
      "title": "lecture-genius/ai-lecture-summarizer",
      "source_url": "https://github.com/lecture-genius/ai-lecture-summarizer",
      "artifact_type": "starter_template",
      "summary": "Full-stack starter that turns lecture recordings into summaries, flashcards, and quizzes.",
      "why_relevant": "Matches your project because it targets lecture/video content with summarization and study features you can remix.",
      "how_to_remix": "Swap the transcription source for your own audio, change the quiz prompt template, and reuse the Supabase schema.",
      "setup_commands": ["git clone https://github.com/lecture-genius/ai-lecture-summarizer", "pnpm install", "pnpm dev"],
      "frameworks": ["Next.js", "Supabase", "Tailwind"],
      "tools": ["Whisper", "Supabase", "pgvector"],
      "quality_score": 82,
      "remixability_score": 78
    }
  ]
}
```

---

### 3. `get_artifact_details`

Full artifact by UUID (from search results).

**Input example:**

```json
{
  "artifact_id": "00000000-0000-0000-0000-000000000004"
}
```

**Output example** (fields include everything in search, plus):

```json
{
  "id": "00000000-0000-0000-0000-000000000004",
  "title": "mcphub/repo-search-mcp",
  "source_type": "github",
  "artifact_type": "mcp_server",
  "what_it_helps_build": "An MCP server that exposes repo search + file read tools to Claude Code, Cursor, and Cline.",
  "technical_core": "Implements the MCP stdio transport in TypeScript, wraps the GitHub search and contents APIs...",
  "practical_use_case": "Anyone wiring code-search capabilities into a coding agent.",
  "implementation_steps": ["Clone and npm install", "npm run build", "Add the server to your MCP client config"],
  "setup_commands": ["git clone https://github.com/mcphub/repo-search-mcp", "npm install", "npm run build"],
  "languages": ["TypeScript"],
  "apis": [],
  "models": [],
  "has_code": true,
  "has_demo": false,
  "has_docs": true,
  "applicability_score": 82,
  "underground_score": 80,
  "popularity_score": 16,
  "license": "MIT"
}
```

---

### 4. `recommend_stack`

Aggregate frameworks/tools/languages from top matching artifacts (**no LLM**).

**Input example:**

```json
{
  "project_description": "Full-stack AI SaaS with auth, billing, and streaming chat",
  "constraints": ["TypeScript", "open source friendly"]
}
```

**Output example:**

```json
{
  "frameworks": ["Next.js", "Supabase", "Tailwind", "FastAPI"],
  "tools": ["Stripe", "OpenAI", "Vercel AI SDK", "Supabase"],
  "languages": ["TypeScript", "Python"],
  "based_on_artifacts": 12,
  "sample_artifacts": [
    {
      "id": "00000000-0000-0000-0000-000000000007",
      "title": "supastart/supabase-ai-saas",
      "source_url": "https://github.com/supastart/supabase-ai-saas"
    }
  ],
  "note": "Stack suggestions are aggregated from indexed artifacts matching your description. Use get_artifact_details on specific IDs for setup steps and remix guidance."
}
```

---

## Manual tool testing (without an agent)

With the API running, you can invoke tool logic directly:

```bash
cd apps/mcp
npm run build
node --input-type=module -e "
import { searchArtifacts } from './dist/tools/searchArtifacts.js';
process.env.API_BASE_URL = 'http://localhost:8000';
const r = await searchArtifacts({ query: 'MCP server for coding agents', limit: 3 });
console.log(JSON.stringify(r, null, 2));
"
```

See also `examples/tool-examples.json` for copy-paste inputs/outputs.

## Typical agent workflow

1. **`search_artifacts`** or **`find_similar_projects`** with the user’s project description  
2. **`get_artifact_details`** on 1–3 promising UUIDs for setup commands and remix notes  
3. **`recommend_stack`** if the user asks what stack similar builders use  
4. Agent synthesizes a plan — Build Radar does not call an LLM

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `API not reachable` on stderr | Start FastAPI; check `API_BASE_URL` |
| Empty `results` | Run DB seed + optional embedding backfill |
| MCP not listed in Cursor | Restart IDE; verify absolute path in config |
| `401` / GitHub errors | N/A — MCP only hits Build Radar API |

## Architecture

```
Coding Agent  ←stdio→  apps/mcp (this server)  ←HTTP→  apps/api (FastAPI)  ←→  PostgreSQL
```

No database driver in the MCP package.

### Same search API as the web UI

Both the frontend and MCP call **`GET /search`** with identical query params via `packages/shared/searchQuery.ts` (mirrored in `apps/web/src/lib/searchQuery.ts` and `apps/mcp/src/searchQuery.ts`).

Example path both produce:

`/search?q=RAG+Chrome+extension&limit=20&max_hype_risk=45`

Search never triggers crawlers — only reads pre-indexed Postgres (FTS + pgvector).
