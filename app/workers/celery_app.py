"""Celery application factory."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "clipper",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks.ingest",
        "app.workers.tasks.transcribe",
        "app.workers.tasks.analyze",
        "app.workers.tasks.render",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
)
