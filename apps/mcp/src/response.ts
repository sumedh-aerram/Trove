import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";

/** Return structured JSON for the coding agent to parse and reason over. */
export function jsonResult(data: unknown): CallToolResult {
  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(data, null, 2),
      },
    ],
  };
}
