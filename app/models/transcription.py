"""Structured transcription output models."""

from pydantic import BaseModel, Field


class WordTimestamp(BaseModel):
    word: str
    start: float = Field(ge=0, description="Start time in seconds")
    end: float = Field(ge=0, description="End time in seconds")
    probability: float = Field(ge=0, le=1, description="Model confidence score")


class TranscriptSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    words: list[WordTimestamp]


class TranscriptResult(BaseModel):
    job_id: str
    audio_path: str
    language: str
    language_probability: float
    duration_seconds: float
    full_text: str
    word_count: int
    segments: list[TranscriptSegment]
