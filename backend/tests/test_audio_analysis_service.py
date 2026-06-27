from unittest.mock import AsyncMock, patch

import pytest

from app.services.audio_analysis_service import (
    analyse_video_audio_style,
    resolve_local_video_path,
)
from app.services.web_video_fetch import DownloadAttemptResult


@pytest.mark.asyncio
async def test_resolve_local_video_path_returns_existing_file(tmp_path):
    video_file = tmp_path / "reference.mp4"
    video_file.write_bytes(b"fake-video")

    resolved = await resolve_local_video_path(
        project_id="proj_1",
        video_path=str(video_file),
    )
    assert resolved == str(video_file)


@pytest.mark.asyncio
async def test_resolve_local_video_path_downloads_from_url():
    download_result = DownloadAttemptResult(
        success=True,
        local_file_path="/tmp/reference/youtube_123.mp4",
        source_url="https://www.youtube.com/watch?v=abc123",
    )
    with patch(
        "app.services.audio_analysis_service.WebVideoFetchService.download_video_url",
        new=AsyncMock(return_value=download_result),
    ):
        resolved = await resolve_local_video_path(
            project_id="proj_1",
            video_url="https://www.youtube.com/watch?v=abc123",
            subdir="reference",
        )

    assert resolved == "/tmp/reference/youtube_123.mp4"


@pytest.mark.asyncio
async def test_resolve_local_video_path_returns_none_for_invalid_url():
    resolved = await resolve_local_video_path(
        project_id="proj_1",
        video_url="https://example.com/blog/post",
    )
    assert resolved is None


@pytest.mark.asyncio
async def test_analyse_video_audio_style_merges_gemini_and_slng_for_url():
    download_result = DownloadAttemptResult(
        success=True,
        local_file_path="/tmp/reference/youtube_123.mp4",
        source_url="https://www.youtube.com/watch?v=abc123",
    )
    slng_style = {
        "transcript_sample": "Welcome to my ranking video",
        "has_speech": True,
        "estimated_style": "voice_first",
        "confidence": 0.75,
    }

    with patch(
        "app.services.audio_analysis_service.WebVideoFetchService.download_video_url",
        new=AsyncMock(return_value=download_result),
    ), patch(
        "app.services.audio_analysis_service.SLNGAudioClient.analyse_audio_style",
        new=AsyncMock(return_value=slng_style),
    ):
        result = await analyse_video_audio_style(
            project_id="proj_1",
            video_url="https://www.youtube.com/watch?v=abc123",
            subdir="reference",
        )

    assert result is not None
    assert result.audio_style == slng_style
    assert result.local_file_path == "/tmp/reference/youtube_123.mp4"


@pytest.mark.asyncio
async def test_analyse_video_audio_style_uses_local_file_without_caching_path(tmp_path):
    video_file = tmp_path / "reference.mp4"
    video_file.write_bytes(b"fake-video")
    slng_style = {
        "transcript_sample": "Rank five",
        "has_speech": True,
        "estimated_style": "voice_first",
        "confidence": 0.75,
    }

    with patch(
        "app.services.audio_analysis_service.SLNGAudioClient.analyse_audio_style",
        new=AsyncMock(return_value=slng_style),
    ) as mock_analyse:
        result = await analyse_video_audio_style(
            project_id="proj_1",
            video_path=str(video_file),
            subdir="reference",
        )

    mock_analyse.assert_awaited_once_with(str(video_file))
    assert result is not None
    assert result.audio_style == slng_style
    assert result.local_file_path is None
