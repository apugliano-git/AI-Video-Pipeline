"""Celery task: audio transcription with word-level timestamps."""

import logging
from pathlib import Path
from uuid import UUID

from app.models.domain import JobStatus
from app.services.job_store import JobRepository
from app.services.transcription.whisper_service import WhisperService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.transcribe_audio", bind=True, max_retries=1)
def transcribe_audio_task(self, ingest_result: dict) -> dict:
    """
    Transcribe audio produced by ingest_media_task.

    Receives the ingest task return value via Celery chain:
        chain(ingest_media_task.s(...), transcribe_audio_task.s())
    """
    repo = JobRepository()
    whisper = WhisperService()

    job_id = ingest_result["job_id"]
    audio_path = ingest_result["audio_path"]
    uid = UUID(job_id)

    try:
        repo.update(
            uid,
            status=JobStatus.TRANSCRIBING,
            progress=35,
            message="Transcribing audio with Whisper",
        )

        transcript, output_path = whisper.transcribe_and_save(
            Path(audio_path),
            job_id,
        )

        repo.update(
            uid,
            status=JobStatus.TRANSCRIBED,
            progress=50,
            message=(
                f"Transcribed {transcript.word_count} words "
                f"({transcript.language}, {transcript.duration_seconds:.1f}s)"
            ),
            transcript_path=str(output_path),
        )

        return {
            **ingest_result,
            "transcript_path": str(output_path),
            "language": transcript.language,
            "word_count": transcript.word_count,
            "duration_seconds": transcript.duration_seconds,
            "full_text": transcript.full_text,
        }

    except Exception as exc:
        logger.exception("Transcription failed for job %s", job_id)
        if self.request.retries >= self.max_retries:
            repo.update(
                uid,
                status=JobStatus.FAILED,
                progress=25,
                message="Transcription failed after retries",
                error=str(exc),
            )
            raise
        repo.update(
            uid,
            message=f"Retrying transcription (attempt {self.request.retries + 1})",
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=60) from exc
