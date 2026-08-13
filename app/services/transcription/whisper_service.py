"""Local speech-to-text via faster-whisper with word-level timestamps."""

import json
import logging
from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel

from app.core.config import Settings, get_settings
from app.models.transcription import TranscriptResult, TranscriptSegment, WordTimestamp

logger = logging.getLogger(__name__)


class WhisperService:
    """Transcribes audio files and produces structured JSON with word timestamps."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._model: WhisperModel | None = None

    @property
    def model(self) -> WhisperModel:
        if self._model is None:
            logger.info(
                "Loading Whisper model '%s' (device=%s, compute=%s)",
                self.settings.whisper_model,
                self.settings.whisper_device,
                self.settings.whisper_compute_type,
            )
            self._model = WhisperModel(
                self.settings.whisper_model,
                device=self.settings.whisper_device,
                compute_type=self.settings.whisper_compute_type,
            )
        return self._model

    def transcribe(self, audio_path: Path, job_id: str) -> TranscriptResult:
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info("Transcribing audio for job %s: %s", job_id, audio_path.name)

        segments_iter, info = self.model.transcribe(
            str(audio_path),
            language=self.settings.whisper_language or None,
            word_timestamps=True,
            vad_filter=True,
        )

        segments: list[TranscriptSegment] = []
        full_text_parts: list[str] = []
        word_count = 0

        for segment_id, segment in enumerate(segments_iter):
            words = [
                WordTimestamp(
                    word=word.word.strip(),
                    start=round(word.start, 3),
                    end=round(word.end, 3),
                    probability=round(word.probability, 4),
                )
                for word in segment.words or []
            ]
            word_count += len(words)
            text = segment.text.strip()
            full_text_parts.append(text)

            segments.append(
                TranscriptSegment(
                    id=segment_id,
                    start=round(segment.start, 3),
                    end=round(segment.end, 3),
                    text=text,
                    words=words,
                )
            )

        full_text = " ".join(full_text_parts).strip()
        duration = info.duration if info.duration else 0.0

        result = TranscriptResult(
            job_id=job_id,
            audio_path=str(audio_path),
            language=info.language or "unknown",
            language_probability=round(info.language_probability or 0.0, 4),
            duration_seconds=round(duration, 3),
            full_text=full_text,
            word_count=word_count,
            segments=segments,
        )

        logger.info(
            "Transcription complete for job %s — %d words, language=%s",
            job_id,
            word_count,
            result.language,
        )
        return result

    def transcribe_and_save(self, audio_path: Path, job_id: str) -> tuple[TranscriptResult, Path]:
        result = self.transcribe(audio_path, job_id)
        output_path = Path(audio_path).parent / "transcript.json"
        output_path.write_text(
            json.dumps(result.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Transcript saved to %s", output_path)
        return result, output_path


@lru_cache
def get_whisper_service() -> WhisperService:
    return WhisperService()
