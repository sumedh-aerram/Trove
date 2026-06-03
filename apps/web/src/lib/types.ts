export interface Artifact {
  id: string;
  title: string;
  slug: string;
  source_type: string;
  artifact_type: string;
  source_url: string;
  canonical_url?: string;
  author_name?: string;
  summary?: string;
  what_it_helps_build?: string;
  technical_core?: string;
  practical_use_case?: string;
  how_to_remix?: string;
  implementation_steps?: string[];
  setup_commands?: string[];
  tags?: string[];
  tools?: string[];
  frameworks?: string[];
  languages?: string[];
  apis?: string[];
  models?: string[];
  has_code?: boolean;
  has_demo?: boolean;
  has_docs?: boolean;
  quality_score?: number;
  remixability_score?: number;
  underground_score?: number;
  hype_risk_score?: number;
  popularity_score?: number;
  why_relevant?: string;
  final_score?: number;
}

export interface SearchResponse {
  query: string;
  intent: Record<string, unknown>;
  results: Artifact[];
  total: number;
}

export interface ArtifactListResponse {
  items: Artifact[];
  total: number;
  limit: number;
  offset: number;
}

export interface ProfileResponse {
  profile: {
    id: string;
    username: string;
    display_name?: string;
    bio?: string;
    credibility_score: number;
  };
  starred_artifacts_count: number;
}
