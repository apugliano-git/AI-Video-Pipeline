"""Pydantic request/response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.models.domain import JobStatus


class CreateJobRequest(BaseModel):
    url: HttpUrl = Field(..., description="YouTube video URL (16:9 long-form content)")


class JobResponse(BaseModel):
    id: UUID
    source_url: str
    status: JobStatus
    progress: int = Field(ge=0, le=100, description="Overall pipeline progress (0-100)")
    message: str | None = None
    video_path: str | None = None
    audio_path: str | None = None
    transcript_path: str | None = None
    analysis_path: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
