/**
 * Ensures web and MCP build identical /search URLs.
 */
import { buildSearchPath as webPath } from "../src/lib/searchQuery";
import { buildSearchPath as mcpPath } from "../../mcp/src/searchQuery";

const input = {
  q: "RAG Chrome extension for research papers",
  limit: 20,
  framework: "TypeScript",
  max_hype_risk: 45,
};

const web = webPath(input);
const mcp = mcpPath(input);

if (web !== mcp) {
  console.error("Mismatch:\n  web:", web, "\n  mcp:", mcp);
  process.exit(1);
}
console.log("OK: web and MCP search paths match");
