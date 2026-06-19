"""Pydantic request/response schemas."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class ArtifactOut(BaseModel):
    id: str
    title: str
    slug: str
    source_type: str
    artifact_type: str
    source_url: str
    canonical_url: Optional[str] = None
    author_name: Optional[str] = None
    author_url: Optional[str] = None
    summary: Optional[str] = None
    what_it_helps_build: Optional[str] = None
    technical_core: Optional[str] = None
    practical_use_case: Optional[str] = None
    how_to_remix: Optional[str] = None
    implementation_steps: list[str] = Field(default_factory=list)
    setup_commands: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    apis: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    has_code: bool = False
    has_demo: bool = False
    has_docs: bool = False
    has_paper: bool = False
    has_license: bool = False
    license: Optional[str] = None
    difficulty: Optional[str] = None
    estimated_time_to_integrate: Optional[str] = None
    published_at: Optional[str] = None
    quality_score: float = 0
    remixability_score: float = 0
    applicability_score: float = 0
    underground_score: float = 0
    hype_risk_score: float = 0
    popularity_score: float = 0

    model_config = {"extra": "allow"}


class ArtifactListResponse(BaseModel):
    items: list[ArtifactOut]
    total: int
    limit: int
    offset: int


class SearchResultOut(ArtifactOut):
    why_relevant: str = ""
    final_score: float = 0
    project_relevance_score: float = 0
    # Landscape fields (populated by landscape_service).
    relevance: float = 0
    relevance_pct: int = 0
    confidence: str = ""
    cluster_id: str = ""
    cluster_label: str = ""
    headline: str = ""
    key_points: list[str] = Field(default_factory=list)
    use_case: str = ""
    simple_implementation: str = ""
    start_steps: list[str] = Field(default_factory=list)
    top_rank: int = 999
    about: str = ""
    how_it_helps: str = ""
    stands_out: list[str] = Field(default_factory=list)


class LandscapeCluster(BaseModel):
    id: str
    label: str
    count: int


class SearchResponse(BaseModel):
    query: str
    intent: dict[str, Any] = Field(default_factory=dict)
    results: list[SearchResultOut]
    total: int
    clusters: list[LandscapeCluster] = Field(default_factory=list)
    landscape_summary: str = ""
    query_confidence: int = 0
    query_advice: str = ""
    suggested_query: str = ""


class StarRequest(BaseModel):
    username: str


class ProfileResponse(BaseModel):
    profile: dict[str, Any]
    starred_artifacts_count: int = 0


class LeaderboardEntry(BaseModel):
    username: str
    display_name: Optional[str] = None
    credibility_score: float = 0


class LeaderboardResponse(BaseModel):
    profiles: list[LeaderboardEntry]
