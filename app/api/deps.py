"""FastAPI dependency injection."""

from functools import lru_cache

from app.services.job_store import JobRepository


@lru_cache
def get_job_repository() -> JobRepository:
    return JobRepository()
