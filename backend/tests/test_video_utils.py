from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import video_utils


@pytest.fixture(autouse=True)
def clear_ffmpeg_cache() -> None:
    video_utils.resolve_ffmpeg_binary.cache_clear()
    video_utils.ffmpeg_supports_drawtext.cache_clear()


@pytest.mark.asyncio
async def test_add_text_overlay_copies_source_when_drawtext_unavailable(tmp_path: Path) -> None:
    source_path = tmp_path / "source.mp4"
    output_path = tmp_path / "output.mp4"
    source_path.write_bytes(b"video-bytes")

    with patch("app.services.video_utils.ffmpeg_supports_drawtext", return_value=False):
        result = await video_utils.add_text_overlay(
            str(source_path),
            str(output_path),
            "Hook text",
        )

    assert result == str(output_path)
    assert output_path.read_bytes() == source_path.read_bytes()


@pytest.mark.asyncio
async def test_add_text_overlay_uses_ffmpeg_when_drawtext_available(tmp_path: Path) -> None:
    source_path = tmp_path / "source.mp4"
    output_path = tmp_path / "output.mp4"
    source_path.write_bytes(b"video-bytes")

    with (
        patch("app.services.video_utils.ffmpeg_supports_drawtext", return_value=True),
        patch("app.services.video_utils.run_ffmpeg_command") as mock_run_ffmpeg,
    ):
        result = await video_utils.add_text_overlay(
            str(source_path),
            str(output_path),
            "Rank #1",
            start_sec=0.0,
            duration_sec=2.0,
        )

    assert result == str(output_path)
    mock_run_ffmpeg.assert_awaited_once()
    ffmpeg_args = mock_run_ffmpeg.await_args.args[0]
    assert "-vf" in ffmpeg_args
    assert "drawtext=text='Rank #1'" in ffmpeg_args[ffmpeg_args.index("-vf") + 1]


def test_resolve_ffmpeg_binary_prefers_drawtext_enabled_build() -> None:
    with (
        patch("app.services.video_utils._binary_is_executable", return_value=True),
        patch("app.services.video_utils._ffmpeg_has_filter") as mock_has_filter,
    ):
        mock_has_filter.side_effect = lambda binary, _filter_name: binary.endswith("ffmpeg-full/bin/ffmpeg")

        selected = video_utils.resolve_ffmpeg_binary()

    assert selected == "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"


def test_resolve_ffprobe_binary_matches_selected_ffmpeg() -> None:
    with patch("app.services.video_utils.resolve_ffmpeg_binary", return_value="/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"):
        ffprobe_binary = video_utils.resolve_ffprobe_binary()

    assert ffprobe_binary == "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe"
