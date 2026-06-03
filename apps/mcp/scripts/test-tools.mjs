#!/usr/bin/env node
/**
 * Smoke-test MCP tool handlers against a running API (no stdio MCP protocol).
 * Usage: API_BASE_URL=http://localhost:8000 npm run test:tools
 */
import { searchArtifacts } from "../dist/tools/searchArtifacts.js";
import { findSimilarProjects } from "../dist/tools/findSimilarProjects.js";
import { recommendStack } from "../dist/tools/recommendStack.js";

const base = process.env.API_BASE_URL || "http://localhost:8000";
console.error(`Testing tools against ${base}\n`);

const search = await searchArtifacts({
  query: "MCP server for coding agents",
  limit: 2,
});
console.log("search_artifacts:", JSON.stringify(search, null, 2).slice(0, 800), "...\n");

const similar = await findSimilarProjects({
  project_description: "RAG Chrome extension for research papers",
  current_stack: ["TypeScript"],
  limit: 2,
});
console.log("find_similar_projects:", JSON.stringify(similar, null, 2).slice(0, 600), "...\n");

const stack = await recommendStack({
  project_description: "AI lecture summarizer with quiz",
});
console.log("recommend_stack:", JSON.stringify(stack, null, 2));

if (search.results.length === 0) {
  console.error("\nFAIL: no search results — is the API running with seed data?");
  process.exit(1);
}
console.error("\nOK");
