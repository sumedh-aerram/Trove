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

    # HNSW recall/latency knob: how many candidates the index explores per probe.
    # Default pgvector value is 40; raising it improves vector recall for a few ms.
    hnsw_ef_search: int = 200

    # Pseudo-relevance feedback (vector-side Rocchio). Eval-gated; see
    # scripts/eval_search.py. Expands the query embedding toward the centroid of
    # the top-k first-pass hits (no FTS noise). Default off until it beats baseline.
    prf_enabled: bool = False
    prf_top_k: int = 5
    prf_beta: float = 0.5

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
    # Tuned via scripts/tune_search.py (nested-CV nDCG@10 0.458 -> 0.562):
    # looser final/relevance gates recover retrieval recall; stricter vector
    # escape trims noisy low-similarity matches from the weak 384d embeddings.
    search_min_project_relevance: float = 0.11
    search_min_final_score: float = 0.19
    search_min_vector_similarity: float = 0.43

    # Stage-2 learned reranker (LightGBM LambdaMART over hand-crafted features).
    # Trained + nested-CV validated by scripts/train_ltr.py (held-out nDCG@10
    # 0.605 -> 0.629). No model download, scores in microseconds. Falls back to
    # the linear blend if the model file or lightgbm is missing.
    ltr_enabled: bool = True

    # Maximal Marginal Relevance: reorder top results to reduce near-duplicate
    # themes (variety over pure relevance). Eval-gated; lambda=1.0 is pure
    # relevance, lower trades relevance for diversity.
    mmr_enabled: bool = False
    mmr_lambda: float = 0.7

    # Stage-2 cross-encoder reranking (retrieve-then-rerank).
    # Disabled by default: the eval harness (scripts/eval_search.py) shows the
    # general-domain ms-marco reranker significantly underperforms stage-1 hybrid
    # on this dev-tool corpus (nDCG@10 0.67 vs 0.83, p<0.05). Re-enable only with a
    # model that beats stage-1 in the eval (e.g. a domain-tuned bge reranker).
    rerank_enabled: bool = False
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_candidates: int = 12
    rerank_weight: float = 0.45  # blend: weight*rerank + (1-weight)*hybrid_score

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
