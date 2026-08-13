"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health, jobs
from app.core.config import get_settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    setup_logging(debug=settings.debug)
    settings.ensure_storage_dirs()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="SaaS pipeline for AI-powered video clipping and reframing.",
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(jobs.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
