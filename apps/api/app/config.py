"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://postgres:postgres@localhost:5433/build_radar"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Comma-separated list of allowed CORS origins.
    cors_origins: str = "http://localhost:3000"

    web_base_url: str = "http://localhost:3000"

    # Background indexing is handled by the always-on crawler daemon, so search
    # never spawns crawls (keeps queries fast and the CPU cool).
    background_crawl_on_search: bool = False
    background_crawl_enabled: bool = True
    background_crawl_stale_minutes: int = 30
    background_crawl_github_stale_minutes: int = 60
    background_crawl_cooldown_minutes: int = 30

    bootstrap_crawl_on_start: bool = False
    bootstrap_min_artifacts: int = 40

    # Drop weak matches (improves precision for local indexes).
    search_min_project_relevance: float = 0.2
    search_min_final_score: float = 0.25
    search_min_vector_similarity: float = 0.32

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
