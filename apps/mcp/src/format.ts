import type {
  ArtifactDetails,
  ArtifactSearchResult,
  SimilarProjectResult,
} from "./types.js";

function str(v: unknown, fallback = ""): string {
  return v != null ? String(v) : fallback;
}

function arr(v: unknown): string[] {
  return Array.isArray(v) ? (v as string[]) : [];
}

function num(v: unknown, fallback = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

/** Map API search hit → MCP search_artifacts result row. */
export function toSearchResult(row: Record<string, unknown>): ArtifactSearchResult {
  return {
    id: str(row.id),
    title: str(row.title),
    source_url: str(row.source_url),
    artifact_type: str(row.artifact_type),
    summary: str(row.summary),
    why_relevant: str(row.why_relevant),
    how_to_remix: str(row.how_to_remix),
    implementation_steps: arr(row.implementation_steps),
    setup_commands: arr(row.setup_commands),
    tags: arr(row.tags),
    frameworks: arr(row.frameworks),
    tools: arr(row.tools),
    quality_score: num(row.quality_score),
    remixability_score: num(row.remixability_score),
    hype_risk_score: num(row.hype_risk_score),
  };
}

/** Map API search hit → find_similar_projects result row. */
export function toSimilarProject(row: Record<string, unknown>): SimilarProjectResult {
  const base = toSearchResult(row);
  return {
    id: base.id,
    title: base.title,
    source_url: base.source_url,
    artifact_type: base.artifact_type,
    summary: base.summary,
    why_relevant: base.why_relevant,
    how_to_remix: base.how_to_remix,
    setup_commands: base.setup_commands,
    frameworks: base.frameworks,
    tools: base.tools,
    quality_score: base.quality_score,
    remixability_score: base.remixability_score,
  };
}

/** Map full API artifact → get_artifact_details payload. */
export function toArtifactDetails(row: Record<string, unknown>): ArtifactDetails {
  const base = toSearchResult(row);
  return {
    ...base,
    source_type: str(row.source_type),
    what_it_helps_build: str(row.what_it_helps_build),
    technical_core: str(row.technical_core),
    practical_use_case: str(row.practical_use_case),
    languages: arr(row.languages),
    apis: arr(row.apis),
    models: arr(row.models),
    has_code: Boolean(row.has_code),
    has_demo: Boolean(row.has_demo),
    has_docs: Boolean(row.has_docs),
    applicability_score: num(row.applicability_score),
    underground_score: num(row.underground_score),
    popularity_score: num(row.popularity_score),
    license: row.license != null ? str(row.license) : undefined,
  };
}
