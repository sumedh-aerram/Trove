#!/usr/bin/env node
/**
 * Trove MCP server — connects coding agents to the FastAPI backend.
 *
 * - No Postgres access
 * - No LLM calls
 * - Returns structured JSON for the agent to reason over
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { checkApiHealth, getApiBaseUrl } from "./client.js";
import { jsonResult } from "./response.js";
import { findSimilarProjects } from "./tools/findSimilarProjects.js";
import { getArtifactDetails } from "./tools/getArtifactDetails.js";
import { recommendStack } from "./tools/recommendStack.js";
import { searchArtifacts } from "./tools/searchArtifacts.js";

const server = new McpServer({
  name: "trove",
  version: "0.1.0",
});

server.tool(
  "search_artifacts",
  `Search Trove for open-source projects, techniques, starter templates, APIs, models, MCP servers, coding-agent workflows, and implementation recipes.

Use a full project-context query (what you are building, stack, goals). Returns structured artifacts with scores and why_relevant — no LLM reasoning in this tool.`,
  {
    query: z
      .string()
      .describe(
        "Natural-language project context, e.g. 'RAG Chrome extension for research papers using Next.js'",
      ),
    frameworks: z.array(z.string()).optional().describe("Filter/boost: Next.js, Supabase, etc."),
    languages: z.array(z.string()).optional().describe("Filter/boost: TypeScript, Python, etc."),
    tools: z.array(z.string()).optional().describe("Filter/boost: LangChain, Whisper, MCP, etc."),
    artifact_types: z
      .array(z.string())
      .optional()
      .describe("e.g. starter_template, mcp_server, open_source_project"),
    source_type: z
      .string()
      .optional()
      .describe("github | hackernews | arxiv | user_submission"),
    min_quality_score: z.number().optional().describe("0-100 quality floor"),
    max_hype_risk: z.number().optional().describe("0-100 hype ceiling"),
    limit: z.number().int().min(1).max(50).optional().describe("Max results (default 10)"),
  },
  async (input) => jsonResult(await searchArtifacts(input)),
);

server.tool(
  "find_similar_projects",
  `Find open-source projects similar to the user's project that can be remixed.

Constructs a search from project_description + optional stack/features. Returns remixable repos with why_relevant.`,
  {
    project_description: z
      .string()
      .describe("What the user is building in plain language"),
    current_stack: z
      .array(z.string())
      .optional()
      .describe("Frameworks/tools already chosen, e.g. ['Next.js', 'Supabase']"),
    desired_features: z
      .array(z.string())
      .optional()
      .describe("Features to add, e.g. ['RAG', 'quiz generation']"),
    limit: z.number().int().min(1).max(50).optional(),
  },
  async (input) => jsonResult(await findSimilarProjects(input)),
);

server.tool(
  "get_artifact_details",
  "Fetch full Trove artifact by UUID: summary, remix steps, setup commands, stack tags, and scores.",
  {
    artifact_id: z.string().uuid().describe("Artifact UUID from search results"),
  },
  async (input) => jsonResult(await getArtifactDetails(input)),
);

server.tool(
  "recommend_stack",
  `Suggest common frameworks, tools, and languages from artifacts that match the project description.

Frequency-based aggregation only — no LLM. Your agent should validate choices against get_artifact_details.`,
  {
    project_description: z.string(),
    constraints: z
      .array(z.string())
      .optional()
      .describe("Hard constraints, e.g. ['TypeScript only', 'no vendor lock-in']"),
  },
  async (input) => jsonResult(await recommendStack(input)),
);

async function main() {
  const apiOk = await checkApiHealth();
  if (apiOk) {
    console.error(`[trove-mcp] Connected to API at ${getApiBaseUrl()}`);
  } else {
    console.error(
      `[trove-mcp] WARNING: API not reachable at ${getApiBaseUrl()} — start FastAPI first (uvicorn app.main:app --port 8000)`,
    );
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("[trove-mcp] Fatal:", err);
  process.exit(1);
});
