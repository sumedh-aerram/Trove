/** Structured tool outputs — no LLM reasoning, API data only. */

export interface ArtifactSearchResult {
  id: string;
  title: string;
  source_url: string;
  artifact_type: string;
  summary: string;
  why_relevant: string;
  how_to_remix: string;
  implementation_steps: string[];
  setup_commands: string[];
  tags: string[];
  frameworks: string[];
  tools: string[];
  quality_score: number;
  remixability_score: number;
  hype_risk_score: number;
}

export interface SimilarProjectResult {
  id: string;
  title: string;
  source_url: string;
  artifact_type: string;
  summary: string;
  why_relevant: string;
  how_to_remix: string;
  setup_commands: string[];
  frameworks: string[];
  tools: string[];
  quality_score: number;
  remixability_score: number;
}

export interface ArtifactDetails extends ArtifactSearchResult {
  source_type: string;
  what_it_helps_build: string;
  technical_core: string;
  practical_use_case: string;
  languages: string[];
  apis: string[];
  models: string[];
  has_code: boolean;
  has_demo: boolean;
  has_docs: boolean;
  applicability_score: number;
  underground_score: number;
  popularity_score: number;
  license?: string;
}

export interface RecommendStackResult {
  frameworks: string[];
  tools: string[];
  languages: string[];
  based_on_artifacts: number;
  sample_artifacts: Array<{ id: string; title: string; source_url: string }>;
  note: string;
}

export interface SearchArtifactsOutput {
  results: ArtifactSearchResult[];
}

export interface FindSimilarProjectsOutput {
  results: SimilarProjectResult[];
}
