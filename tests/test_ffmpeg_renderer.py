"""Unit tests for FFmpeg renderer."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.services.render.ffmpeg_renderer import render_clip, RenderResult


def test_render_clip_raises_if_source_not_found(tmp_path: Path):
    non_existent_video = tmp_path / "missing.mp4"
    sub_file = tmp_path / "sub.ass"
    sub_file.write_text("dummy")
    out_file = tmp_path / "output.mp4"

    with pytest.raises(FileNotFoundError):
        render_clip(non_existent_video, sub_file, 0.0, 30.0, out_file)


def test_render_clip_successful_subprocess(tmp_path: Path):
    source_video = tmp_path / "source.mp4"
    source_video.write_text("fake video data")
    sub_file = tmp_path / "sub.ass"
    sub_file.write_text("dummy sub")
    out_file = tmp_path / "output.mp4"

    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stderr = ""

    with patch("app.services.render.ffmpeg_renderer._get_available_video_encoder", return_value=("libx264", ["-crf", "20", "-preset", "fast"])):
        with patch("subprocess.run", return_value=mock_run) as mock_subprocess:
            result = render_clip(
                source_video=source_video,
                subtitle_file=sub_file,
                hook_start=10.0,
                hook_end=45.0,
                output_path=out_file,
            )

            assert isinstance(result, RenderResult)
            assert result.duration_seconds == 35.0
            assert result.output_path == out_file

            mock_subprocess.assert_called_once()
            args = mock_subprocess.call_args[0][0]
        assert args[0] == "ffmpeg"
        assert "-ss" in args
        assert "10.0" in args
        assert "-t" in args
        assert "35.0" in args


def test_render_clip_raises_on_ffmpeg_failure(tmp_path: Path):
    source_video = tmp_path / "source.mp4"
    source_video.write_text("fake video")
    sub_file = tmp_path / "sub.ass"
    sub_file.write_text("sub")
    out_file = tmp_path / "out.mp4"

    mock_run = MagicMock()
    mock_run.returncode = 1
    mock_run.stderr = "Invalid crop filter"

    with patch("subprocess.run", return_value=mock_run):
        with pytest.raises(RuntimeError, match="FFmpeg failed with exit code 1"):
            render_clip(source_video, sub_file, 0.0, 30.0, out_file)
