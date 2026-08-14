"""Celery Canvas orchestration for the processing pipeline."""

from celery import chain
from celery.result import AsyncResult

from app.workers.tasks.ingest import ingest_media_task
from app.workers.tasks.transcribe import transcribe_audio_task
from app.workers.tasks.analyze import analyze_hook_task
from app.workers.tasks.render import render_clip_task


def enqueue_pipeline(job_id: str, source_url: str) -> AsyncResult:
    """
    Enqueue the full 4-stage processing pipeline as a Celery chain.

    Stages (each receives the previous task's return dict):
      1. ingest_media_task   — yt-dlp download + audio extraction
      2. transcribe_audio_task — faster-whisper STT with word timestamps
      3. analyze_hook_task   — LLM viral hook detection
      4. render_clip_task    — FFmpeg 9:16 render + subtitle burn-in
    """
    workflow = chain(
        ingest_media_task.s(job_id, source_url),
        transcribe_audio_task.s(),
        analyze_hook_task.s(),
        render_clip_task.s(),
    )
    return workflow.apply_async()
