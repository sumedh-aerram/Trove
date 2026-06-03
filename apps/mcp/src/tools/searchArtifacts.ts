import { apiGet, buildSearchPath } from "../client.js";
import { toSearchResult } from "../format.js";
import type { SearchArtifactsOutput } from "../types.js";

export type SearchArtifactsInput = {
  query: string;
  frameworks?: string[];
  languages?: string[];
  tools?: string[];
  artifact_types?: string[];
  source_type?: string;
  min_quality_score?: number;
  max_hype_risk?: number;
  limit?: number;
};

export async function searchArtifacts(
  input: SearchArtifactsInput,
): Promise<SearchArtifactsOutput> {
  const path = buildSearchPath({
    q: input.query,
    limit: input.limit ?? 10,
    artifact_type: input.artifact_types?.[0],
    source_type: input.source_type,
    framework: input.frameworks?.[0],
    language: input.languages?.[0],
    tool: input.tools?.[0],
    min_quality_score: input.min_quality_score,
    max_hype_risk: input.max_hype_risk,
  });
  const data = await apiGet<{ results: Array<Record<string, unknown>> }>(path);
  return {
    results: (data.results || []).map(toSearchResult),
  };
}
