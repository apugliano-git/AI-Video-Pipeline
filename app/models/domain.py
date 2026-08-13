"""Domain enums and constants."""

from enum import StrEnum


class JobStatus(StrEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStage(StrEnum):
    INGEST = "ingest"
    TRANSCRIBE = "transcribe"
    ANALYZE = "analyze"
    RENDER = "render"
