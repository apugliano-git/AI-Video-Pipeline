"""
Supabase Storage service for uploading rendered video clips.

Provides seamless upload to a Supabase Storage bucket using HTTP REST API (httpx),
with an automatic graceful fallback to the local filesystem if Supabase credentials
are not configured.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StorageUploadResult:
    url: str
    is_remote: bool
    storage_path: str


class SupabaseStorageService:
    """Manages video uploads to Supabase Storage with local filesystem fallback."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.supabase_url.strip() and self.settings.supabase_key.strip())

    def upload_clip(self, file_path: Path, job_id: str) -> StorageUploadResult:
        """
        Uploads a rendered clip to Supabase Storage if configured.
        Otherwise, returns a local storage reference.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File to upload not found: {file_path}")

        file_name = f"{job_id}_{file_path.name}"

        if not self.is_configured:
            logger.info(
                "Supabase credentials not configured. Using local storage fallback for job %s: %s",
                job_id,
                file_path,
            )
            return StorageUploadResult(
                url=f"file://{file_path.resolve()}",
                is_remote=False,
                storage_path=str(file_path.resolve()),
            )

        # Upload to Supabase Storage API
        bucket = self.settings.supabase_bucket
        base_url = self.settings.supabase_url.rstrip("/")
        upload_endpoint = f"{base_url}/storage/v1/object/{bucket}/{file_name}"
        public_url = f"{base_url}/storage/v1/object/public/{bucket}/{file_name}"

        headers = {
            "Authorization": f"Bearer {self.settings.supabase_key}",
            "apikey": self.settings.supabase_key,
            "Content-Type": "video/mp4",
            "x-upsert": "true",
        }

        try:
            logger.info("Uploading %s to Supabase bucket '%s'...", file_name, bucket)
            with file_path.open("rb") as f:
                content = f.read()

            with httpx.Client(timeout=60.0) as client:
                response = client.post(upload_endpoint, headers=headers, content=content)

            if response.status_code in (200, 201):
                logger.info("Successfully uploaded clip to Supabase: %s", public_url)
                return StorageUploadResult(
                    url=public_url,
                    is_remote=True,
                    storage_path=f"{bucket}/{file_name}",
                )
            else:
                logger.warning(
                    "Supabase upload returned status %s: %s. Falling back to local.",
                    response.status_code,
                    response.text,
                )
                return StorageUploadResult(
                    url=f"file://{file_path.resolve()}",
                    is_remote=False,
                    storage_path=str(file_path.resolve()),
                )

        except Exception as exc:
            logger.warning(
                "Failed to upload to Supabase (%s). Falling back to local storage.",
                exc,
            )
            return StorageUploadResult(
                url=f"file://{file_path.resolve()}",
                is_remote=False,
                storage_path=str(file_path.resolve()),
            )
