import { apiGet, buildSearchPath } from "../client.js";
import { toSimilarProject } from "../format.js";
import type { FindSimilarProjectsOutput } from "../types.js";

export type FindSimilarProjectsInput = {
  project_description: string;
  current_stack?: string[];
  desired_features?: string[];
  limit?: number;
};

export async function findSimilarProjects(
  input: FindSimilarProjectsInput,
): Promise<FindSimilarProjectsOutput> {
  const parts = [input.project_description.trim()];
  if (input.current_stack?.length) {
    parts.push(`Stack: ${input.current_stack.join(", ")}`);
  }
  if (input.desired_features?.length) {
    parts.push(`Features: ${input.desired_features.join(", ")}`);
  }

  const path = buildSearchPath({
    q: parts.join(". "),
    limit: input.limit ?? 10,
  });
  const data = await apiGet<{ results: Array<Record<string, unknown>> }>(path);
  return {
    results: (data.results || []).map(toSimilarProject),
  };
}
