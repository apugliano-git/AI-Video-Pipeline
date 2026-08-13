"""Celery task: render the final 9:16 clip with burned subtitles."""

import json
import logging
from pathlib import Path
from uuid import UUID

from app.models.analysis import HookAnalysisResult
from app.models.domain import JobStatus
from app.models.transcription import TranscriptResult
from app.services.job_store import JobRepository
from app.services.render.ffmpeg_renderer import render_clip
from app.services.render.subtitle_generator import generate_ass
from app.services.storage.supabase_service import SupabaseStorageService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.render_clip", bind=True, max_retries=1)
def render_clip_task(self, analyze_result: dict) -> dict:
    """
    Final pipeline stage: generate subtitles, render the clip, and upload to storage.

    Receives the output dict from analyze_hook_task via the Celery chain.
    Expected keys in analyze_result:
      - job_id           (str UUID)
      - video_path       (str)
      - transcript_path  (str)
      - analysis_path    (str)
      - hook_start       (float)
      - hook_end         (float)
      - hook_title       (str)

    Outputs:
      - storage/downloads/{job_id}/subtitles.ass
      - storage/downloads/{job_id}/final_clip.mp4

    Updates job status in Redis:
      RENDERING (85%) → COMPLETED (100%)
    """
    repo = JobRepository()
    storage = SupabaseStorageService()
    job_id = analyze_result["job_id"]
    uid = UUID(job_id)

    try:
        repo.update(
            uid,
            status=JobStatus.RENDERING,
            progress=85,
            message="Rendering final clip with subtitles",
        )

        # ── Resolve paths ─────────────────────────────────────────────────────
        video_path = Path(analyze_result["video_path"])
        transcript_path = Path(analyze_result["transcript_path"])
        analysis_path = Path(analyze_result["analysis_path"])

        job_dir = video_path.parent
        subtitle_path = job_dir / "subtitles.ass"
        output_path = job_dir / "final_clip.mp4"

        # ── Load models from disk ─────────────────────────────────────────────
        transcript = TranscriptResult.model_validate_json(transcript_path.read_text())
        hook = HookAnalysisResult.model_validate(json.loads(analysis_path.read_text()))

        # ── Step 1: Generate .ass subtitle file ───────────────────────────────
        generate_ass(
            transcript=transcript,
            hook=hook,
            output_path=subtitle_path,
        )

        # ── Step 2: Render clip with FFmpeg ───────────────────────────────────
        render_result = render_clip(
            source_video=video_path,
            subtitle_file=subtitle_path,
            hook_start=hook.start_seconds,
            hook_end=hook.end_seconds,
            output_path=output_path,
        )

        # ── Step 3: Upload to Cloud or Local Fallback ─────────────────────────
        upload_result = storage.upload_clip(output_path, job_id)

        # ── Step 4: Mark job as completed ─────────────────────────────────────
        repo.update(
            uid,
            status=JobStatus.COMPLETED,
            progress=100,
            message=f"Clip ready: {analyze_result['hook_title']}",
            final_clip_path=str(output_path),
            clip_url=upload_result.url,
        )

        logger.info("Pipeline complete for job %s → %s", job_id, upload_result.url)

        return {
            **analyze_result,
            "subtitle_path": str(subtitle_path),
            "final_clip_path": str(output_path),
            "clip_url": upload_result.url,
            "render_duration_seconds": render_result.duration_seconds,
        }

    except Exception as exc:
        logger.exception("Render failed for job %s", job_id)
        if self.request.retries >= self.max_retries:
            repo.update(
                uid,
                status=JobStatus.FAILED,
                progress=85,
                message="Render failed after retries",
                error=str(exc),
            )
            raise
        repo.update(
            uid,
            message=f"Retrying render (attempt {self.request.retries + 1})",
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=30) from exc
