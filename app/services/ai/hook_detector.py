"""Viral hook detection via Groq (Llama) or Google Gemini."""

import json
import logging
from pathlib import Path

import httpx

from app.core.config import Settings, get_settings
from app.models.analysis import HookAnalysisResult
from app.models.transcription import TranscriptResult

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_PROMPT = """You are an expert viral short-form content strategist.
Analyze the timestamped transcript and select the single most engaging 30-75 second segment
(preferably 60-75 seconds for optimal monetization) that would work as a vertical clip (TikTok/Reels/Shorts).

Prioritize segments with:
- Strong emotional hooks or surprising statements
- Clear narrative payoff within 30-75 seconds
- High energy, humor, controversy, or actionable insight
- Self-contained context (understandable without prior setup)

Respond ONLY with valid JSON matching this exact schema:
{
  "start_seconds": <float in seconds, e.g. 145.2>,
  "end_seconds": <float in seconds, e.g. 210.5>,
  "hook_title": "<short catchy title, max 120 chars>",
  "reasoning": "<technical justification for virality>",
  "confidence_score": <float 0.0-1.0>
}

Rules:
- (end_seconds - start_seconds) MUST be between 30 and 75 seconds
- start_seconds and end_seconds MUST be positive float seconds (e.g. 120.5) taken directly from the bracketed seconds in the transcript
- end_seconds MUST NOT exceed the total video duration
- Do not invent content outside the transcript
"""


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_transcript_for_prompt(transcript: TranscriptResult) -> str:
    lines = [
        f"Total Video duration: {transcript.duration_seconds:.1f} seconds ({format_timestamp(transcript.duration_seconds)})",
        f"Language: {transcript.language}",
        f"Word count: {transcript.word_count}",
        "",
        "Timestamped transcript (seconds are in brackets):",
    ]
    for segment in transcript.segments:
        start_fmt = format_timestamp(segment.start)
        end_fmt = format_timestamp(segment.end)
        lines.append(f"[{segment.start:.1f}s ({start_fmt}) - {segment.end:.1f}s ({end_fmt})] {segment.text.strip()}")
    return "\n".join(lines)


def load_transcript(path: Path) -> TranscriptResult:
    return TranscriptResult.model_validate_json(path.read_text(encoding="utf-8"))


class HookDetector:
    """Detects the best viral hook segment using an LLM provider."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.Client(timeout=120.0)

    def detect(self, transcript: TranscriptResult) -> HookAnalysisResult:
        prompt = format_transcript_for_prompt(transcript)
        provider = self._resolve_provider()

        logger.info("Analyzing hook for job %s via %s", transcript.job_id, provider)
        raw_json = self._call_llm(provider, prompt)
        analysis = HookAnalysisResult.model_validate_json(raw_json)
        return analysis.validate_within_video(transcript.duration_seconds)

    def detect_from_file(self, transcript_path: Path) -> HookAnalysisResult:
        transcript = load_transcript(transcript_path)
        return self.detect(transcript)

    def detect_and_save(
        self,
        transcript_path: Path,
        job_id: str,
    ) -> tuple[HookAnalysisResult, Path]:
        analysis = self.detect_from_file(transcript_path)
        output_path = transcript_path.parent / "clip_analysis.json"
        output_path.write_text(
            json.dumps(analysis.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(
            "Hook analysis saved for job %s — %.1fs-%.1fs (%s)",
            job_id,
            analysis.start_seconds,
            analysis.end_seconds,
            analysis.hook_title,
        )
        return analysis, output_path

    def _resolve_provider(self) -> str:
        provider = self.settings.llm_provider.lower()
        if provider == "groq":
            if not self.settings.groq_api_key:
                raise ValueError("LLM_PROVIDER=groq but GROQ_API_KEY is not set")
            return "groq"
        if provider == "gemini":
            if not self.settings.google_ai_api_key:
                raise ValueError("LLM_PROVIDER=gemini but GOOGLE_AI_API_KEY is not set")
            return "gemini"
        if self.settings.groq_api_key:
            return "groq"
        if self.settings.google_ai_api_key:
            return "gemini"
        raise ValueError("No LLM API key configured (set GROQ_API_KEY or GOOGLE_AI_API_KEY)")

    def _call_llm(self, provider: str, prompt: str) -> str:
        if provider == "groq":
            return self._call_groq(prompt)
        return self._call_gemini(prompt)

    def _call_groq(self, prompt: str) -> str:
        response = self._client.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {self.settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.groq_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return content

    def _call_gemini(self, prompt: str) -> str:
        url = GEMINI_API_URL.format(model=self.settings.gemini_model)
        response = self._client.post(
            url,
            params={"key": self.settings.google_ai_api_key},
            json={
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.3,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
