"""Tests for HookDetector with mocked LLM provider."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.analysis import HookAnalysisResult
from app.models.transcription import TranscriptResult, TranscriptSegment
from app.services.ai.hook_detector import HookDetector
from app.core.config import Settings


def test_hook_detector_groq():
    settings = Settings(
        llm_provider="groq",
        groq_api_key="fake-groq-key",
        google_ai_api_key="fake-gemini-key",
    )
    detector = HookDetector(settings=settings)
    
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "start_seconds": 10.0,
                        "end_seconds": 45.0,
                        "hook_title": "Test Hook Title",
                        "reasoning": "Highly engaging segment",
                        "confidence_score": 0.95
                    })
                }
            }
        ]
    }
    
    transcript = TranscriptResult(
        job_id="test-job-123",
        audio_path="fake/path.mp3",
        language="en",
        language_probability=0.99,
        duration_seconds=60.0,
        word_count=100,
        full_text="Hello this is a viral hook",
        segments=[
            TranscriptSegment(
                id=0,
                text="Hello this is a viral hook",
                start=0.0,
                end=60.0,
                words=[]
            )
        ]
    )
    
    with patch.object(detector._client, "post", return_value=mock_response) as mock_post:
        result = detector.detect(transcript)
        
        assert isinstance(result, HookAnalysisResult)
        assert result.start_seconds == 10.0
        assert result.end_seconds == 45.0
        assert result.hook_title == "Test Hook Title"
        assert result.confidence_score == 0.95
        
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.groq.com/openai/v1/chat/completions"
        assert call_args[1]["headers"]["Authorization"] == "Bearer fake-groq-key"
