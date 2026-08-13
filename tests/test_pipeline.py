"""Tests for Celery pipeline chain wiring."""

from unittest.mock import MagicMock, patch

from app.workers.pipeline import enqueue_ingest_and_transcribe


@patch("app.workers.pipeline.chain")
def test_enqueue_ingest_and_transcribe_builds_chain(mock_chain):
    mock_workflow = MagicMock()
    mock_async_result = MagicMock()
    mock_workflow.apply_async.return_value = mock_async_result
    mock_chain.return_value = mock_workflow

    result = enqueue_ingest_and_transcribe("job-id", "https://youtube.com/watch?v=abc")

    mock_chain.assert_called_once()
    mock_workflow.apply_async.assert_called_once()
    assert result is mock_async_result
