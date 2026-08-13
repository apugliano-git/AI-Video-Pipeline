"""Unit tests for SupabaseStorageService."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.core.config import Settings
from app.services.storage.supabase_service import SupabaseStorageService, StorageUploadResult


def test_storage_fallback_when_not_configured(tmp_path: Path):
    settings = Settings(supabase_url="", supabase_key="")
    service = SupabaseStorageService(settings=settings)
    
    dummy_file = tmp_path / "clip.mp4"
    dummy_file.write_bytes(b"dummy mp4 content")
    
    result = service.upload_clip(dummy_file, "job-123")
    
    assert isinstance(result, StorageUploadResult)
    assert result.is_remote is False
    assert "file://" in result.url
    assert str(dummy_file.resolve()) in result.url


def test_storage_upload_success_when_configured(tmp_path: Path):
    settings = Settings(
        supabase_url="https://xyz.supabase.co",
        supabase_key="fake-key",
        supabase_bucket="clips",
    )
    service = SupabaseStorageService(settings=settings)
    
    dummy_file = tmp_path / "clip.mp4"
    dummy_file.write_bytes(b"dummy mp4 content")
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    
    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        result = service.upload_clip(dummy_file, "job-123")
        
        assert result.is_remote is True
        assert result.url == "https://xyz.supabase.co/storage/v1/object/public/clips/job-123_clip.mp4"
        mock_post.assert_called_once()
