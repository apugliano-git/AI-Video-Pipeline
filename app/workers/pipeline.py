"""Celery Canvas orchestration for the processing pipeline."""

from celery import chain
from celery.result import AsyncResult

from app.workers.tasks.ingest import ingest_media_task
from app.workers.tasks.transcribe import transcribe_audio_task
from app.workers.tasks.analyze import analyze_hook_task


def enqueue_ingest_and_transcribe(job_id: str, source_url: str) -> AsyncResult:
    """
    Run ingest → transcribe as an atomic Celery chain.

    Each task is independent and receives only the data it needs:
      - ingest_media_task(job_id, source_url) → ingest payload
      - transcribe_audio_task(ingest_payload) → enriched payload
    """
    workflow = chain(
        ingest_media_task.s(job_id, source_url),
        transcribe_audio_task.s(),
        analyze_hook_task.s(),
    )
    return workflow.apply_async()
