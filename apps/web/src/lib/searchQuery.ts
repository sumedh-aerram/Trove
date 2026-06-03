/** Canonical GET /search params — keep in sync with packages/shared/searchQuery.ts and apps/mcp/src/searchQuery.ts */

export type SearchQueryInput = {
  q: string;
  limit?: number;
  artifact_type?: string;
  source_type?: string;
  framework?: string;
  language?: string;
  tool?: string;
  min_quality_score?: number;
  max_hype_risk?: number;
};

export function buildSearchPath(params: SearchQueryInput): string {
  const qs = new URLSearchParams();
  qs.set("q", params.q.trim());
  qs.set("limit", String(params.limit ?? 20));

  if (params.artifact_type) qs.set("artifact_type", params.artifact_type);
  if (params.source_type) qs.set("source_type", params.source_type);
  if (params.framework) qs.set("framework", params.framework);
  if (params.language) qs.set("language", params.language);
  if (params.tool) qs.set("tool", params.tool);
  if (params.min_quality_score != null) {
    qs.set("min_quality_score", String(params.min_quality_score));
  }
  if (params.max_hype_risk != null) {
    qs.set("max_hype_risk", String(params.max_hype_risk));
  }

  return `/search?${qs.toString()}`;
}
