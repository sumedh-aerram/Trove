import type { Artifact, ArtifactListResponse, ProfileResponse, SearchResponse } from "./types";
import { buildSearchPath, type SearchQueryInput } from "./searchQuery";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const FETCH_TIMEOUT_MS = 12_000;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    signal: controller.signal,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  }).finally(() => clearTimeout(timeout));
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export function getApiUrl(): string {
  return API_URL;
}

export interface IndexStats {
  artifact_count: number;
  embeddings_count: number;
  last_crawl_at: string | null;
  last_updated_at?: string | null;
  last_new_at?: string | null;
  added_last_hour?: number;
  added_today?: number;
  crawl_by_source: Record<string, string | null>;
  search_mode: string;
  crawl_in_progress?: boolean;
  background_crawl_enabled?: boolean;
  index_is_sparse?: boolean;
  note?: string;
}

export function getStats(): Promise<IndexStats> {
  return request("/stats");
}

export function listArtifacts(params?: Record<string, string | number>): Promise<ArtifactListResponse> {
  const qs = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => qs.set(k, String(v)));
  }
  const q = qs.toString();
  return request(`/artifacts${q ? `?${q}` : ""}`);
}

export function getArtifact(id: string): Promise<Artifact> {
  return request(`/artifacts/${id}`);
}

/** Same GET /search endpoint as MCP search_artifacts tool. */
export function searchArtifacts(params: SearchQueryInput): Promise<SearchResponse> {
  return request(buildSearchPath(params));
}

export function starArtifact(id: string, username: string) {
  return request(`/artifacts/${id}/star`, {
    method: "POST",
    body: JSON.stringify({ username }),
  });
}

export function unstarArtifact(id: string, username: string) {
  return request(`/artifacts/${id}/star`, {
    method: "DELETE",
    body: JSON.stringify({ username }),
  });
}

export function getProfile(username: string): Promise<ProfileResponse> {
  return request(`/profiles/${username}`);
}
