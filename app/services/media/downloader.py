"""YouTube media ingestion via yt-dlp."""

import logging
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DownloadResult:
    video_path: Path
    audio_path: Path
    title: str
    duration_seconds: float | None


class MediaDownloader:
    """Downloads video and extracts audio using yt-dlp + FFmpeg post-processing."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def download(self, url: str, job_id: str) -> DownloadResult:
        job_dir = self.settings.downloads_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        video_template = str(job_dir / "video.%(ext)s")
        audio_template = str(job_dir / "audio.%(ext)s")

        logger.info("Starting download for job %s: %s", job_id, url)

        video_info = self._download_video(url, video_template)
        audio_path = self._extract_audio(url, audio_template)

        video_path = Path(video_info["filepath"])
        title = video_info.get("title", "untitled")
        duration = video_info.get("duration")

        logger.info(
            "Download complete for job %s — video: %s, audio: %s",
            job_id,
            video_path.name,
            audio_path.name,
        )

        return DownloadResult(
            video_path=video_path,
            audio_path=audio_path,
            title=title,
            duration_seconds=float(duration) if duration else None,
        )

    def _download_video(self, url: str, output_template: str) -> dict:
        opts = {
            "format": self.settings.ytdlp_format,
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            if not filepath.endswith(".mp4"):
                filepath = str(Path(filepath).with_suffix(".mp4"))
            return {
                "title": info.get("title"),
                "duration": info.get("duration"),
                "filepath": filepath,
            }

    def _extract_audio(self, url: str, output_template: str) -> Path:
        opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": self.settings.ytdlp_audio_format,
                    "preferredquality": "192",
                }
            ],
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)

        audio_path = Path(output_template.replace("%(ext)s", self.settings.ytdlp_audio_format))
        if not audio_path.exists():
            candidates = list(Path(output_template).parent.glob(f"audio.*"))
            if not candidates:
                raise FileNotFoundError(f"Audio extraction failed for {url}")
            audio_path = candidates[0]

        return audio_path
