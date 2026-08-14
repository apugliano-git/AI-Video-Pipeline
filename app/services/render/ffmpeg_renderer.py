"""
FFmpeg rendering engine for the viral hook clip.

Responsibilities:
  1. Trim the source video to [hook_start, hook_end].
  2. Reframe to vertical 9:16 using a blurred background layout:
       - Background: the 16:9 frame zoomed + blurred to fill 1080x1920.
       - Foreground: the original 16:9 frame centered on top, fully visible.
  3. Burn the .ass subtitle file directly into the video stream.
  4. Pass the audio stream through with re-encode to AAC (no filter_complex
     involvement — avoids PTS desync issues when using fast-seek with -ss).

All steps are executed in a SINGLE FFmpeg pass.

Why subprocess over a Python FFmpeg wrapper library?
  - FFmpeg's filter_complex syntax is expressive but brittle when wrapped by
    third-party libraries. Using subprocess with an explicit argument list gives
    full control over every flag and avoids hidden incompatibilities between
    library versions and the locally installed FFmpeg binary.
"""

import logging
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Output video settings ─────────────────────────────────────────────────────
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920

AUDIO_CODEC = "aac"
AUDIO_BITRATE = "192k"


@lru_cache(maxsize=1)
def _get_available_video_encoder() -> tuple[str, list[str]]:
    """
    Probe the locally installed FFmpeg binary for the best available H.264
    software encoder.  Returns (encoder_name, extra_encoder_flags).

    Priority: libx264 (best quality/speed) → libopenh264 (Fedora default) →
              h264_nvenc (NVIDIA GPU) → h264_vaapi (VA-API) → libx264 fallback.
    """
    try:
        res = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
        out = res.stdout
        if "libx264" in out:
            return "libx264", ["-crf", "20", "-preset", "fast"]
        if "libopenh264" in out:
            return "libopenh264", []
        if "h264_nvenc" in out:
            return "h264_nvenc", ["-preset", "p4"]
        if "h264_vaapi" in out:
            return "h264_vaapi", []
    except Exception:
        pass
    return "libx264", ["-crf", "20", "-preset", "fast"]


@dataclass(frozen=True)
class RenderResult:
    output_path: Path
    duration_seconds: float


def render_clip(
    source_video: Path,
    subtitle_file: Path,
    hook_start: float,
    hook_end: float,
    output_path: Path,
) -> RenderResult:
    """
    Execute the full render pipeline in a single FFmpeg call.

    Args:
        source_video:  Path to the original downloaded .mp4 file.
        subtitle_file: Path to the .ass subtitle file from subtitle_generator.
        hook_start:    Start time of the hook in the source video (seconds).
        hook_end:      End time of the hook in the source video (seconds).
        output_path:   Destination path for the rendered final_clip.mp4.

    Returns:
        RenderResult containing the output path and duration in seconds.

    Raises:
        FileNotFoundError: If source_video does not exist.
        RuntimeError:      If FFmpeg exits with a non-zero return code.
    """
    if not source_video.exists():
        raise FileNotFoundError(f"Source video not found: {source_video}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    hook_duration = hook_end - hook_start

    # On Linux the ASS filter requires a forward-slash path. On Windows
    # backslashes must also be converted (no-op on Linux/Mac).
    ass_path = str(subtitle_file.resolve()).replace("\\", "/")

    # ── Video filter_complex ──────────────────────────────────────────────────
    #
    # Two-layer vertical layout:
    #
    # Layer 1 – Background [bg]:
    #   Scale the 16:9 input to *at least* 1080x1920 (force_original_aspect_ratio=increase),
    #   then center-crop to exactly 1080x1920, and apply a heavy boxblur.
    #   This fills the black bars that would appear above/below the foreground.
    #
    # Layer 2 – Foreground [fg]:
    #   Scale the 16:9 input to exactly OUTPUT_WIDTH wide, keeping aspect ratio
    #   (height = 607 px for a 1920×1080 source).  Centered vertically.
    #
    # Composite: overlay the sharp foreground on the blurred background,
    #   horizontally centered, vertically centered: (W-w)/2, (H-h)/2.
    #
    # Subtitles: burn the .ass file onto the composited canvas.
    #
    # Audio: NOT processed here. The audio stream is mapped directly from the
    #   input (-map 0:a) and re-encoded to AAC outside the filter_complex.
    #   Mixing audio into filter_complex alongside -ss causes PTS desync on
    #   some containers (notably AV1/AAC from YouTube downloads) that makes the
    #   resulting audio track appear empty in desktop players.
    #
    filter_complex = (
        f"[0:v]split=2[bg_in][fg_in];"
        f"[bg_in]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}"
        f":force_original_aspect_ratio=increase,"
        f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},"
        f"boxblur=20:5[bg];"
        f"[fg_in]scale={OUTPUT_WIDTH}:-1[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[combined];"
        f"[combined]ass='{ass_path}'[vout]"
    )

    encoder, encoder_flags = _get_available_video_encoder()

    cmd = [
        "ffmpeg",
        "-y",                        # overwrite output without asking
        "-ss", str(hook_start),      # fast seek before the input (keyframe-accurate)
        "-i", str(source_video),     # single input file
        "-t", str(hook_duration),    # duration to encode (not end timestamp)
        "-filter_complex", filter_complex,
        "-map", "[vout]",            # processed video stream
        "-map", "0:a",               # original audio stream (bypasses filter_complex)
        "-c:v", encoder,
        *encoder_flags,
        "-c:a", AUDIO_CODEC,
        "-b:a", AUDIO_BITRATE,
        "-movflags", "+faststart",   # move MP4 metadata to front for streaming
        str(output_path),
    ]

    logger.info(
        "Starting FFmpeg render for hook [%.2fs – %.2fs] → %s",
        hook_start,
        hook_end,
        output_path,
    )
    logger.debug("FFmpeg command: %s", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error("FFmpeg stderr:\n%s", result.stderr)
        raise RuntimeError(
            f"FFmpeg failed with exit code {result.returncode}.\n"
            f"stderr: {result.stderr[-3000:]}"
        )

    logger.info(
        "Render complete: %s (%.1fs clip)",
        output_path,
        hook_duration,
    )

    return RenderResult(
        output_path=output_path,
        duration_seconds=hook_duration,
    )
