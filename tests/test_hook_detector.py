"""Tests for HookDetector with mocked LLM provider."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.models.analysis import HookAnalysisResult
from app.models.transcription import TranscriptResult, TranscriptSegment
from app.services.ai.hook_detector import HookDetector


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_transcript(duration: float = 60.0) -> TranscriptResult:
    return TranscriptResult(
        job_id="test-job-123",
        audio_path="fake/path.wav",
        language="en",
        language_probability=0.99,
        duration_seconds=duration,
        word_count=100,
        full_text="Hello this is a viral hook",
        segments=[
            TranscriptSegment(
                id=0,
                text="Hello this is a viral hook",
                start=0.0,
                end=duration,
                words=[],
            )
        ],
    )


def _groq_response_json(start: float = 10.0, end: float = 45.0) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "start_seconds": start,
                            "end_seconds": end,
                            "hook_title": "Test Hook Title",
                            "reasoning": "Highly engaging segment",
                            "confidence_score": 0.95,
                        }
                    )
                }
            }
        ]
    }


def _gemini_response_json(start: float = 10.0, end: float = 45.0) -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "start_seconds": start,
                                    "end_seconds": end,
                                    "hook_title": "Test Gemini Hook",
                                    "reasoning": "Viral segment reasoning",
                                    "confidence_score": 0.88,
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_hook_detector_groq():
    """Groq provider: detect() calls Groq API and parses result correctly."""
    settings = Settings(llm_provider="groq", groq_api_key="fake-groq-key")
    detector = HookDetector(settings=settings)

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = _groq_response_json()

    # Patch httpx.Client so the context manager returns our mock
    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_instance.post.return_value = mock_response

    with patch("app.services.ai.hook_detector.httpx.Client", return_value=mock_client_instance):
        result = detector.detect(_make_transcript())

    assert isinstance(result, HookAnalysisResult)
    assert result.start_seconds == 10.0
    assert result.end_seconds == 45.0
    assert result.hook_title == "Test Hook Title"
    assert result.confidence_score == pytest.approx(0.95)

    mock_client_instance.post.assert_called_once()
    call_url = mock_client_instance.post.call_args[0][0]
    assert "groq.com" in call_url
    auth = mock_client_instance.post.call_args[1]["headers"]["Authorization"]
    assert auth == "Bearer fake-groq-key"


def test_hook_detector_gemini():
    """Gemini provider: detect() calls Gemini API and parses result correctly."""
    settings = Settings(llm_provider="gemini", google_ai_api_key="fake-gemini-key")
    detector = HookDetector(settings=settings)

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = _gemini_response_json()

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_instance.post.return_value = mock_response

    with patch("app.services.ai.hook_detector.httpx.Client", return_value=mock_client_instance):
        result = detector.detect(_make_transcript())

    assert isinstance(result, HookAnalysisResult)
    assert result.hook_title == "Test Gemini Hook"
    assert result.confidence_score == pytest.approx(0.88)

    call_url = mock_client_instance.post.call_args[0][0]
    assert "generativelanguage" in call_url


def test_hook_detector_provider_fallback_to_groq_when_both_keys_set():
    """When provider is unknown, should fall back to groq if key is present."""
    settings = Settings(
        llm_provider="unknown_provider",
        groq_api_key="groq-key",
        google_ai_api_key="gemini-key",
    )
    detector = HookDetector(settings=settings)
    assert detector._resolve_provider() == "groq"


def test_hook_detector_provider_fallback_to_gemini_when_only_gemini_key():
    """When provider is unknown and only Gemini key set, use Gemini."""
    settings = Settings(
        llm_provider="unknown_provider",
        groq_api_key="",
        google_ai_api_key="gemini-key",
    )
    detector = HookDetector(settings=settings)
    assert detector._resolve_provider() == "gemini"


def test_hook_detector_raises_when_no_keys():
    """ValueError when no API keys are configured."""
    settings = Settings(llm_provider="groq", groq_api_key="", google_ai_api_key="")
    detector = HookDetector(settings=settings)
    with pytest.raises(ValueError, match="GROQ_API_KEY is not set"):
        detector._resolve_provider()
