"""Unit tests for FFmpeg renderer."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from app.services.render.ffmpeg_renderer import RenderResult, render_clip


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_encoder(encoder="libx264", flags=None):
    """Return a patch context that stubs _get_available_video_encoder."""
    if flags is None:
        flags = ["-crf", "20", "-preset", "fast"]
    return patch(
        "app.services.render.ffmpeg_renderer._get_available_video_encoder",
        return_value=(encoder, flags),
    )


def _mock_success_run():
    m = MagicMock()
    m.returncode = 0
    m.stderr = ""
    return m


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_render_clip_raises_if_source_not_found(tmp_path: Path):
    """FileNotFoundError when source video path doesn't exist."""
    non_existent_video = tmp_path / "missing.mp4"
    sub_file = tmp_path / "sub.ass"
    sub_file.write_text("dummy")
    out_file = tmp_path / "output.mp4"

    with pytest.raises(FileNotFoundError):
        render_clip(non_existent_video, sub_file, 0.0, 30.0, out_file)


def test_render_clip_successful_subprocess(tmp_path: Path):
    """Happy path: FFmpeg called once with correct duration args."""
    source_video = tmp_path / "source.mp4"
    source_video.write_text("fake video data")
    sub_file = tmp_path / "sub.ass"
    sub_file.write_text("dummy sub")
    out_file = tmp_path / "output.mp4"

    mock_run = _mock_success_run()

    with _mock_encoder():
        with patch("subprocess.run", return_value=mock_run) as mock_subprocess:
            result = render_clip(
                source_video=source_video,
                subtitle_file=sub_file,
                hook_start=10.0,
                hook_end=45.0,
                output_path=out_file,
            )

    assert isinstance(result, RenderResult)
    assert result.duration_seconds == pytest.approx(35.0)
    assert result.output_path == out_file

    mock_subprocess.assert_called_once()
    args = mock_subprocess.call_args[0][0]
    assert args[0] == "ffmpeg"
    assert "-ss" in args
    assert "10.0" in args
    assert "-t" in args
    assert "35.0" in args


def test_render_clip_raises_on_ffmpeg_failure(tmp_path: Path):
    """RuntimeError propagated when FFmpeg exits non-zero."""
    source_video = tmp_path / "source.mp4"
    source_video.write_text("fake video")
    sub_file = tmp_path / "sub.ass"
    sub_file.write_text("sub")
    out_file = tmp_path / "out.mp4"

    mock_run = MagicMock()
    mock_run.returncode = 1
    mock_run.stderr = "Invalid crop filter"

    with _mock_encoder():
        with patch("subprocess.run", return_value=mock_run):
            with pytest.raises(RuntimeError, match="FFmpeg failed with exit code 1"):
                render_clip(source_video, sub_file, 0.0, 30.0, out_file)


def test_render_clip_audio_mapped_directly(tmp_path: Path):
    """Audio must be mapped via '-map 0:a' NOT inside filter_complex."""
    source_video = tmp_path / "source.mp4"
    source_video.write_text("video")
    sub_file = tmp_path / "sub.ass"
    sub_file.write_text("sub")
    out_file = tmp_path / "out.mp4"

    mock_run = _mock_success_run()

    with _mock_encoder():
        with patch("subprocess.run", return_value=mock_run) as mock_subprocess:
            render_clip(source_video, sub_file, 0.0, 30.0, out_file)

    args = mock_subprocess.call_args[0][0]
    # Verify audio is NOT processed inside filter_complex (no aresample/asetpts)
    filter_complex_idx = args.index("-filter_complex")
    filter_str = args[filter_complex_idx + 1]
    assert "aresample" not in filter_str, "Audio should not be inside filter_complex"
    assert "asetpts" not in filter_str, "Audio PTS should not be reset inside filter_complex"
    # Verify direct audio mapping
    assert "-map" in args
    map_indices = [i for i, a in enumerate(args) if a == "-map"]
    mapped_streams = [args[i + 1] for i in map_indices]
    assert "0:a" in mapped_streams, "Audio stream must be mapped directly from input"


def test_render_clip_creates_output_directory(tmp_path: Path):
    """Output parent directory should be created if it doesn't exist."""
    source_video = tmp_path / "source.mp4"
    source_video.write_text("video")
    sub_file = tmp_path / "sub.ass"
    sub_file.write_text("sub")
    nested_out = tmp_path / "nested" / "deep" / "out.mp4"  # does not exist

    mock_run = _mock_success_run()

    with _mock_encoder():
        with patch("subprocess.run", return_value=mock_run):
            render_clip(source_video, sub_file, 0.0, 30.0, nested_out)

    assert nested_out.parent.exists()
