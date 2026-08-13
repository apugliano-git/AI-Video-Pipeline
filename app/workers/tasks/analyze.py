"""Celery task: viral hook detection via LLM."""

import logging
from pathlib import Path
from uuid import UUID

from app.models.domain import JobStatus
from app.services.ai.hook_detector import HookDetector
from app.services.job_store import JobRepository
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.analyze_hook", bind=True, max_retries=1)
def analyze_hook_task(self, transcribe_result: dict) -> dict:
    """
    Analyze transcript and detect the best viral hook segment.

    Receives transcribe_audio_task output via Celery chain.
    """
    repo = JobRepository()
    detector = HookDetector()

    job_id = transcribe_result["job_id"]
    transcript_path = transcribe_result["transcript_path"]
    uid = UUID(job_id)

    try:
        repo.update(
            uid,
            status=JobStatus.ANALYZING,
            progress=65,
            message="Analyzing transcript for viral hook with LLM",
        )

        analysis, output_path = detector.detect_and_save(
            Path(transcript_path),
            job_id,
        )

        repo.update(
            uid,
            status=JobStatus.ANALYZED,
            progress=75,
            message=f"Hook detected: {analysis.hook_title}",
            analysis_path=str(output_path),
        )

        return {
            **transcribe_result,
            "analysis_path": str(output_path),
            "hook_start": analysis.start_seconds,
            "hook_end": analysis.end_seconds,
            "hook_title": analysis.hook_title,
            "hook_duration": analysis.duration_seconds,
            "confidence_score": analysis.confidence_score,
        }

    except Exception as exc:
        logger.exception("Hook analysis failed for job %s", job_id)
        if self.request.retries >= self.max_retries:
            repo.update(
                uid,
                status=JobStatus.FAILED,
                progress=50,
                message="Hook analysis failed after retries",
                error=str(exc),
            )
            raise
        repo.update(
            uid,
            message=f"Retrying hook analysis (attempt {self.request.retries + 1})",
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=30) from exc
