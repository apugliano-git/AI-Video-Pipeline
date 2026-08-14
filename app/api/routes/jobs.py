"""Job lifecycle endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_job_repository
from app.models.schemas import CreateJobRequest, JobResponse
from app.services.job_store import JobRepository
from app.workers.pipeline import enqueue_pipeline

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a YouTube URL for async processing",
)
def create_job(
    payload: CreateJobRequest,
    repo: JobRepository = Depends(get_job_repository),
) -> JobResponse:
    job = repo.create(source_url=str(payload.url))
    enqueue_pipeline(str(job.id), str(payload.url))
    return job


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job status and pipeline progress",
)
def get_job(
    job_id: UUID,
    repo: JobRepository = Depends(get_job_repository),
) -> JobResponse:
    job = repo.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return job
