"""Unit tests for SubtitleGenerator."""

from pathlib import Path
import pytest

from app.models.analysis import HookAnalysisResult
from app.models.transcription import TranscriptResult, TranscriptSegment, WordTimestamp
from app.services.render.subtitle_generator import (
    generate_ass,
    _seconds_to_ass_time,
    _filter_words,
    _recalibrate,
)


def test_seconds_to_ass_time():
    assert _seconds_to_ass_time(0.0) == "0:00:00.00"
    assert _seconds_to_ass_time(65.5) == "0:01:05.50"
    assert _seconds_to_ass_time(3661.25) == "1:01:01.25"


def test_generate_ass_creates_valid_file(tmp_path: Path):
    words = [
        WordTimestamp(word="Hola", start=10.0, end=10.5, probability=0.99),
        WordTimestamp(word="a", start=10.6, end=10.8, probability=0.99),
        WordTimestamp(word="todos", start=10.9, end=11.5, probability=0.98),
        WordTimestamp(word="amigos", start=11.6, end=12.0, probability=0.97),
        WordTimestamp(word="afuera", start=80.0, end=80.5, probability=0.95),  # Outside hook
    ]
    
    transcript = TranscriptResult(
        job_id="test-job",
        audio_path="test/audio.wav",
        language="es",
        language_probability=0.99,
        duration_seconds=100.0,
        full_text="Hola a todos amigos afuera",
        word_count=5,
        segments=[
            TranscriptSegment(
                id=0,
                start=10.0,
                end=12.0,
                text="Hola a todos amigos",
                words=words[:4],
            ),
            TranscriptSegment(
                id=1,
                start=80.0,
                end=80.5,
                text="afuera",
                words=[words[4]],
            ),
        ],
    )
    
    hook = HookAnalysisResult(
        start_seconds=10.0,
        end_seconds=45.0,
        hook_title="Test Hook",
        reasoning="Funny moment",
        confidence_score=0.95,
    )
    
    output_ass = tmp_path / "subtitles.ass"
    result_path = generate_ass(transcript, hook, output_ass)
    
    assert result_path.exists()
    content = result_path.read_text(encoding="utf-8")
    
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "[Events]" in content
    assert "Dialogue:" in content
    assert "Hola" in content
    assert "amigos" in content
    assert "afuera" not in content  # Filtered out correctly
