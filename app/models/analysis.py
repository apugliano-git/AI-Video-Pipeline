"""LLM hook-detection response schema."""

from pydantic import BaseModel, Field, model_validator

MIN_HOOK_DURATION = 30.0
MAX_HOOK_DURATION = 60.0


class HookAnalysisResult(BaseModel):
    start_seconds: float = Field(ge=0, description="Hook start time in seconds")
    end_seconds: float = Field(gt=0, description="Hook end time in seconds")
    hook_title: str = Field(min_length=1, max_length=120, description="Short catchy clip title")
    reasoning: str = Field(min_length=1, description="Why this segment is viral/engaging")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Model confidence (0-1)")

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds

    @model_validator(mode="after")
    def validate_hook_duration(self) -> "HookAnalysisResult":
        duration = self.duration_seconds
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        if not (MIN_HOOK_DURATION <= duration <= MAX_HOOK_DURATION):
            raise ValueError(
                f"Hook duration must be between {MIN_HOOK_DURATION:.0f}s and "
                f"{MAX_HOOK_DURATION:.0f}s, got {duration:.1f}s"
            )
        return self

    def validate_within_video(self, video_duration_seconds: float) -> "HookAnalysisResult":
        if self.end_seconds > video_duration_seconds:
            raise ValueError(
                f"Hook end ({self.end_seconds:.1f}s) exceeds video duration "
                f"({video_duration_seconds:.1f}s)"
            )
        if self.start_seconds > video_duration_seconds:
            raise ValueError(
                f"Hook start ({self.start_seconds:.1f}s) exceeds video duration "
                f"({video_duration_seconds:.1f}s)"
            )
        return self
