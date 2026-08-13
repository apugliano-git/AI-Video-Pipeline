"""
Subtitle generator for viral hook clips.

Takes a TranscriptResult (from Fase 2) and a HookAnalysisResult (from Fase 3),
filters only the words within the hook time window, recalibrates all timestamps
to start from 0:00:00, and writes a styled .ass subtitle file ready for FFmpeg.

Why .ass instead of .srt?
  - .srt only supports plain text per line.
  - .ass (Advanced SubStation Alpha) supports per-word timing, font style,
    colors, shadows and borders — all required for the word-highlight effect
    typical of TikTok/Reels captions.
"""

import logging
from pathlib import Path

from app.models.analysis import HookAnalysisResult
from app.models.transcription import TranscriptResult, WordTimestamp

logger = logging.getLogger(__name__)

# ── Visual style constants ────────────────────────────────────────────────────
# These values control the appearance of the subtitles burned into the video.
# The video canvas is 1080x1920 (9:16 vertical).

FONT_NAME = "Arial"
FONT_SIZE = 18          # points — relatively large for a 1080px-wide vertical video
PRIMARY_COLOR = "&H00FFFFFF"   # white text (BGR hex, not RGB — .ass uses BGR)
ACTIVE_COLOR = "&H0000F5FF"    # yellow highlight for the word being spoken (BGR)
OUTLINE_COLOR = "&H00000000"   # black outline
SHADOW_COLOR = "&H80000000"    # semi-transparent black shadow
OUTLINE_WIDTH = 3
SHADOW_DEPTH = 2
# Vertical position: bottom third, safely above the platform UI buttons.
# MarginV controls distance from the bottom edge in pixels.
MARGIN_V = 220          # pixels from bottom — keeps text above IG/TikTok buttons

# Words per subtitle "group" — how many words appear on screen at once.
# 3 words feels natural and readable at glance speed for short-form video.
WORDS_PER_GROUP = 3


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert a float number of seconds into the ASS timestamp format H:MM:SS.cc"""
    total_centiseconds = int(round(seconds * 100))
    cs = total_centiseconds % 100
    total_seconds = total_centiseconds // 100
    s = total_seconds % 60
    m = (total_seconds // 60) % 60
    h = total_seconds // 3600
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_header(video_width: int = 1080, video_height: int = 1920) -> str:
    """Build the [Script Info] and [V4+ Styles] sections of the .ass file."""
    return f"""\
[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT_NAME},{FONT_SIZE},{PRIMARY_COLOR},{ACTIVE_COLOR},{OUTLINE_COLOR},{SHADOW_COLOR},-1,0,0,0,100,100,0,0,1,{OUTLINE_WIDTH},{SHADOW_DEPTH},2,10,10,{MARGIN_V},1
Style: Highlight,{FONT_NAME},{FONT_SIZE},{ACTIVE_COLOR},{PRIMARY_COLOR},{OUTLINE_COLOR},{SHADOW_COLOR},-1,0,0,0,100,100,0,0,1,{OUTLINE_WIDTH},{SHADOW_DEPTH},2,10,10,{MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _filter_words(
    transcript: TranscriptResult,
    hook_start: float,
    hook_end: float,
) -> list[WordTimestamp]:
    """
    Collect every WordTimestamp whose window overlaps with [hook_start, hook_end].
    Words are pulled from all TranscriptSegments in the result.
    """
    words: list[WordTimestamp] = []
    for segment in transcript.segments:
        for w in segment.words:
            # Keep words that start before the hook ends AND end after the hook starts
            if w.start < hook_end and w.end > hook_start:
                words.append(w)
    return words


def _recalibrate(words: list[WordTimestamp], hook_start: float) -> list[WordTimestamp]:
    """
    Shift all word timestamps so that hook_start becomes t=0.
    This is necessary because FFmpeg cuts the video from 0:00 in the output,
    so the subtitle timestamps must also start from 0.
    """
    return [
        WordTimestamp(
            word=w.word,
            start=max(0.0, w.start - hook_start),
            end=max(0.0, w.end - hook_start),
            probability=w.probability,
        )
        for w in words
    ]


def _build_dialogue_lines(words: list[WordTimestamp]) -> list[str]:
    """
    Group words into batches of WORDS_PER_GROUP and build one ASS Dialogue line
    per group, with karaoke-style \\k tags to highlight each active word.

    The \\k tag tells ASS renderers to switch the color of the next word after
    N centiseconds. Most mobile video players and FFmpeg's ass filter support this.
    """
    lines: list[str] = []
    if not words:
        return lines

    for i in range(0, len(words), WORDS_PER_GROUP):
        group = words[i : i + WORDS_PER_GROUP]
        group_start = group[0].start
        group_end = group[-1].end

        # Build the text with karaoke tags
        text_parts: list[str] = []
        for w in group:
            duration_cs = int(round((w.end - w.start) * 100))
            # \\kf = "karaoke fill" — progressively highlights the word left-to-right
            text_parts.append(f"{{\\kf{duration_cs}}}{w.word.strip()}")

        text = " ".join(text_parts)

        line = (
            f"Dialogue: 0,"
            f"{_seconds_to_ass_time(group_start)},"
            f"{_seconds_to_ass_time(group_end)},"
            f"Default,,0,0,0,,{text}"
        )
        lines.append(line)

    return lines


def generate_ass(
    transcript: TranscriptResult,
    hook: HookAnalysisResult,
    output_path: Path,
) -> Path:
    """
    Main entry point.

    Given a full TranscriptResult and the selected HookAnalysisResult,
    writes an .ass subtitle file to output_path and returns the path.

    Steps:
      1. Filter words to only those within [hook.start_seconds, hook.end_seconds]
      2. Recalibrate timestamps so the clip starts at t=0
      3. Group words into WORDS_PER_GROUP batches
      4. Write the .ass file with header + dialogue lines
    """
    logger.info(
        "Generating .ass subtitles for hook [%.2fs – %.2fs] → %s",
        hook.start_seconds,
        hook.end_seconds,
        output_path,
    )

    words = _filter_words(transcript, hook.start_seconds, hook.end_seconds)
    if not words:
        logger.warning("No words found in hook window — subtitle file will be empty")

    words = _recalibrate(words, hook.start_seconds)
    dialogue_lines = _build_dialogue_lines(words)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write(_ass_header())
        f.write("\n".join(dialogue_lines))
        f.write("\n")

    logger.info("Subtitle file written: %s (%d dialogue lines)", output_path, len(dialogue_lines))
    return output_path
