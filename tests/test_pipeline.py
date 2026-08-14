"""Tests for Celery pipeline chain wiring."""

from unittest.mock import MagicMock, call, patch

from app.workers.pipeline import enqueue_pipeline


@patch("app.workers.pipeline.render_clip_task")
@patch("app.workers.pipeline.analyze_hook_task")
@patch("app.workers.pipeline.transcribe_audio_task")
@patch("app.workers.pipeline.ingest_media_task")
@patch("app.workers.pipeline.chain")
def test_enqueue_pipeline_builds_full_4_stage_chain(
    mock_chain,
    mock_ingest,
    mock_transcribe,
    mock_analyze,
    mock_render,
):
    """enqueue_pipeline must chain all 4 tasks in the correct order."""
    mock_workflow = MagicMock()
    mock_async_result = MagicMock()
    mock_workflow.apply_async.return_value = mock_async_result
    mock_chain.return_value = mock_workflow

    job_id = "test-job-id"
    url = "https://youtube.com/watch?v=abc"

    result = enqueue_pipeline(job_id, url)

    # The chain must be called with 4 task signatures in order
    mock_chain.assert_called_once_with(
        mock_ingest.s(job_id, url),
        mock_transcribe.s(),
        mock_analyze.s(),
        mock_render.s(),
    )
    mock_workflow.apply_async.assert_called_once()
    assert result is mock_async_result
