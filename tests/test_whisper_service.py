"""Tests for WhisperService with mocked model."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.transcription import TranscriptResult
from app.services.transcription.whisper_service import WhisperService


def _make_mock_segment(text: str, start: float, end: float, words: list[tuple]):
    segment = MagicMock()
    segment.text = text
    segment.start = start
    segment.end = end
    segment.words = []
    for word_text, w_start, w_end, prob in words:
        w = MagicMock()
        w.word = word_text
        w.start = w_start
        w.end = w_end
        w.probability = prob
        segment.words.append(w)
    return segment


@patch("app.services.transcription.whisper_service.WhisperModel")
def test_transcribe_returns_word_level_timestamps(mock_model_cls, tmp_path):
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"fake-audio")

    mock_info = MagicMock()
    mock_info.language = "en"
    mock_info.language_probability = 0.98
    mock_info.duration = 3.5

    mock_segments = [
        _make_mock_segment(
            " Hello world",
            0.0,
            2.5,
            [(" Hello", 0.0, 1.0, 0.99), (" world", 1.1, 2.5, 0.97)],
        ),
    ]

    mock_model = MagicMock()
    mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
    mock_model_cls.return_value = mock_model

    service = WhisperService()
    service._model = mock_model

    result = service.transcribe(audio_file, job_id="test-job-123")

    assert isinstance(result, TranscriptResult)
    assert result.job_id == "test-job-123"
    assert result.language == "en"
    assert result.word_count == 2
    assert len(result.segments) == 1
    assert result.segments[0].words[0].word == "Hello"
    assert result.segments[0].words[0].start == 0.0
    assert result.full_text == "Hello world"


@patch("app.services.transcription.whisper_service.WhisperModel")
def test_transcribe_and_save_writes_json(mock_model_cls, tmp_path):
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"fake-audio")

    mock_info = MagicMock()
    mock_info.language = "es"
    mock_info.language_probability = 0.95
    mock_info.duration = 1.0

    mock_segments = [
        _make_mock_segment(" hola", 0.0, 1.0, [(" hola", 0.0, 1.0, 0.92)]),
    ]

    mock_model = MagicMock()
    mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
    mock_model_cls.return_value = mock_model

    service = WhisperService()
    service._model = mock_model

    _, output_path = service.transcribe_and_save(audio_file, job_id="job-abc")

    assert output_path == tmp_path / "transcript.json"
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert '"word_count": 1' in content
    assert '"language": "es"' in content


def test_transcribe_raises_when_audio_missing(tmp_path):
    service = WhisperService()
    service._model = MagicMock()

    with pytest.raises(FileNotFoundError):
        service.transcribe(tmp_path / "missing.wav", job_id="x")
