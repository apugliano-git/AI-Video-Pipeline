"""Celery task: media ingestion (yt-dlp download + audio extraction)."""

import logging
from uuid import UUID

from app.models.domain import JobStatus
from app.services.job_store import JobRepository
from app.services.media.downloader import MediaDownloader
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.ingest_media", bind=True, max_retries=2)
def ingest_media_task(self, job_id: str, source_url: str) -> dict:
    repo = JobRepository()
    downloader = MediaDownloader()
    uid = UUID(job_id)

    try:
        repo.update(
            uid,
            status=JobStatus.DOWNLOADING,
            progress=10,
            message="Downloading video and extracting audio",
        )

        result = downloader.download(source_url, job_id)

        repo.update(
            uid,
            status=JobStatus.DOWNLOADED,
            progress=25,
            message=f"Downloaded: {result.title}",
            video_path=str(result.video_path),
            audio_path=str(result.audio_path),
        )

        return {
            "job_id": job_id,
            "video_path": str(result.video_path),
            "audio_path": str(result.audio_path),
            "title": result.title,
            "duration_seconds": result.duration_seconds,
        }

    except Exception as exc:
        logger.exception("Ingestion failed for job %s", job_id)
        if self.request.retries >= self.max_retries:
            repo.update(
                uid,
                status=JobStatus.FAILED,
                progress=0,
                message="Ingestion failed after retries",
                error=str(exc),
            )
            raise
        repo.update(
            uid,
            message=f"Retrying ingestion (attempt {self.request.retries + 1})",
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=30) from exc
