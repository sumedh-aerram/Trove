import { apiGet, buildSearchPath } from "../client.js";
import type { RecommendStackResult } from "../types.js";

export type RecommendStackInput = {
  project_description: string;
  constraints?: string[];
};

function topCounts(items: string[], n = 8): string[] {
  const counts = new Map<string, number>();
  for (const item of items) {
    const k = item.trim();
    if (!k) continue;
    counts.set(k, (counts.get(k) || 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([k]) => k);
}

export async function recommendStack(
  input: RecommendStackInput,
): Promise<RecommendStackResult> {
  let q = input.project_description.trim();
  if (input.constraints?.length) {
    q += ` ${input.constraints.join(" ")}`;
  }

  const path = buildSearchPath({ q, limit: 25 });
  const data = await apiGet<{ results: Array<Record<string, unknown>> }>(path);
  const results = data.results || [];

  const frameworks: string[] = [];
  const tools: string[] = [];
  const languages: string[] = [];

  for (const r of results) {
    frameworks.push(...((r.frameworks as string[]) || []));
    tools.push(...((r.tools as string[]) || []));
    languages.push(...((r.languages as string[]) || []));
  }

  return {
    frameworks: topCounts(frameworks),
    tools: topCounts(tools),
    languages: topCounts(languages),
    based_on_artifacts: results.length,
    sample_artifacts: results.slice(0, 5).map((r) => ({
      id: String(r.id),
      title: String(r.title),
      source_url: String(r.source_url),
    })),
    note:
      "Stack suggestions are aggregated from indexed artifacts matching your description. " +
      "Use get_artifact_details on specific IDs for setup steps and remix guidance.",
  };
}
