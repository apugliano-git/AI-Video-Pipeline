"""Job persistence backed by Redis (Phase 1). Supabase replaces this in Phase 2+."""

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import redis

from app.core.config import Settings, get_settings
from app.models.domain import JobStatus
from app.models.schemas import JobResponse

logger = logging.getLogger(__name__)

JOB_KEY_PREFIX = "job:"
JOB_INDEX_KEY = "jobs:index"


class JobRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = redis.from_url(self.settings.redis_url, decode_responses=True)

    def _key(self, job_id: UUID) -> str:
        return f"{JOB_KEY_PREFIX}{job_id}"

    def create(self, source_url: str) -> JobResponse:
        now = datetime.now(UTC)
        job = JobResponse(
            id=uuid4(),
            source_url=source_url,
            status=JobStatus.PENDING,
            progress=0,
            message="Job queued for ingestion",
            created_at=now,
            updated_at=now,
        )
        self._save(job)
        self._client.zadd(JOB_INDEX_KEY, {str(job.id): now.timestamp()})
        logger.info("Created job %s for URL %s", job.id, source_url)
        return job

    def get(self, job_id: UUID) -> JobResponse | None:
        raw = self._client.get(self._key(job_id))
        if not raw:
            return None
        return JobResponse.model_validate_json(raw)

    def update(
        self,
        job_id: UUID,
        *,
        status: JobStatus | None = None,
        progress: int | None = None,
        message: str | None = None,
        video_path: str | None = None,
        audio_path: str | None = None,
        transcript_path: str | None = None,
        analysis_path: str | None = None,
        error: str | None = None,
    ) -> JobResponse:
        job = self.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")

        payload = job.model_dump()
        if status is not None:
            payload["status"] = status
        if progress is not None:
            payload["progress"] = progress
        if message is not None:
            payload["message"] = message
        if video_path is not None:
            payload["video_path"] = video_path
        if audio_path is not None:
            payload["audio_path"] = audio_path
        if transcript_path is not None:
            payload["transcript_path"] = transcript_path
        if error is not None:
            payload["error"] = error

        payload["updated_at"] = datetime.now(UTC)
        updated = JobResponse.model_validate(payload)
        self._save(updated)
        return updated

    def _save(self, job: JobResponse) -> None:
        self._client.set(self._key(job.id), job.model_dump_json())

    def ping(self) -> bool:
        try:
            return self._client.ping()
        except redis.RedisError:
            return False
