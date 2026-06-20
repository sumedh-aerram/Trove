"""Trove FastAPI application."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import close_pool, init_pool
from .routes import artifacts, health, profiles, search, stars, stats
from .services.background_crawl import maybe_bootstrap_on_startup
from .services.embedding_service import warmup
from .services.ltr_service import warmup as ltr_warmup
from .services.reranking_service import warmup as rerank_warmup


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    warmup()
    ltr_warmup()
    rerank_warmup()
    await maybe_bootstrap_on_startup()
    yield
    await close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Trove API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(artifacts.router)
    app.include_router(search.router)
    app.include_router(stars.router)
    app.include_router(profiles.router)
    app.include_router(stats.router)

    return app


app = create_app()
