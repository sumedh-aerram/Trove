/**
 * HTTP client for the Build Radar FastAPI backend.
 * Uses the same GET /search contract as apps/web (packages/shared/searchQuery.ts).
 */
import { buildSearchPath, type SearchQueryInput } from "./searchQuery.js";

const API_BASE = (process.env.API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const REQUEST_TIMEOUT_MS = Number(process.env.API_TIMEOUT_MS || 30_000);

export function getApiBaseUrl(): string {
  return API_BASE;
}

export async function apiGet<T>(path: string): Promise<T> {
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const res = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`Build Radar API ${res.status} ${res.statusText}: ${body.slice(0, 400)}`);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(`Build Radar API timeout after ${REQUEST_TIMEOUT_MS}ms: ${url}`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    const data = await apiGet<{ status: string }>("/health");
    return data.status === "ok";
  } catch {
    return false;
  }
}

/** @deprecated Use SearchQueryInput + buildSearchPath — same as web frontend. */
export type SearchQueryParams = SearchQueryInput & {
  query: string;
  frameworks?: string[];
  languages?: string[];
  tools?: string[];
  artifact_types?: string[];
};

export function buildSearchQuery(params: SearchQueryParams): string {
  return buildSearchPath({
    q: params.query,
    limit: params.limit,
    artifact_type: params.artifact_types?.[0] ?? params.artifact_type,
    source_type: params.source_type,
    framework: params.frameworks?.[0] ?? params.framework,
    language: params.languages?.[0] ?? params.language,
    tool: params.tools?.[0] ?? params.tool,
    min_quality_score: params.min_quality_score,
    max_hype_risk: params.max_hype_risk,
  });
}

export { buildSearchPath, type SearchQueryInput };
