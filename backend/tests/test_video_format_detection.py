from app.constants.video_sources import (
    VIDEO_FORMAT_REGULAR,
    VIDEO_FORMAT_SHORTS,
    VIDEO_ORIENTATION_LANDSCAPE,
    VIDEO_ORIENTATION_MOBILE,
    YOUTUBE_SEARCH_MODE_REGULAR,
    YOUTUBE_SEARCH_MODE_SHORTS,
    detect_video_orientation_from_dimensions,
    detect_youtube_video_format,
    is_youtube_shorts_url,
    platform_search_queries_for_mode,
    resolve_youtube_search_mode,
)
from app.services.video_format_detection import (
    VideoFormatDetectionResult,
    detect_video_format_from_blueprint,
    detect_video_format_from_url,
    merge_format_detection_results,
)


def test_detect_youtube_shorts_url():
    url = "https://www.youtube.com/shorts/uHSvwuEMdL0"
    assert is_youtube_shorts_url(url) is True
    assert detect_youtube_video_format(url) == VIDEO_FORMAT_SHORTS


def test_detect_regular_watch_url():
    url = "https://www.youtube.com/watch?v=uHSvwuEMdL0"
    assert detect_youtube_video_format(url) == VIDEO_FORMAT_REGULAR


def test_detect_orientation_from_dimensions():
    assert detect_video_orientation_from_dimensions(1080, 1920) == VIDEO_ORIENTATION_MOBILE
    assert detect_video_orientation_from_dimensions(1920, 1080) == VIDEO_ORIENTATION_LANDSCAPE


def test_resolve_youtube_search_mode():
    assert resolve_youtube_search_mode(VIDEO_ORIENTATION_MOBILE) == YOUTUBE_SEARCH_MODE_SHORTS
    assert resolve_youtube_search_mode(VIDEO_ORIENTATION_LANDSCAPE) == YOUTUBE_SEARCH_MODE_REGULAR


def test_platform_search_queries_for_mode():
    shorts_queries = platform_search_queries_for_mode(YOUTUBE_SEARCH_MODE_SHORTS)
    assert "shorts" in shorts_queries[0]


def test_detect_video_format_from_blueprint():
    result = detect_video_format_from_blueprint("9:16")
    assert result is not None
    assert result.video_orientation == VIDEO_ORIENTATION_MOBILE


def test_merge_format_detection_prefers_url_shorts():
    url_result = detect_video_format_from_url("https://www.youtube.com/shorts/abc123")
    blueprint_result = detect_video_format_from_blueprint("16:9")
    merged = merge_format_detection_results(url_result, blueprint_result)
    assert merged.video_orientation == VIDEO_ORIENTATION_MOBILE


def test_merge_format_detection_preserves_probe_metadata_for_known_orientation():
    url_result = detect_video_format_from_url("https://www.youtube.com/shorts/abc123")
    probe_result = VideoFormatDetectionResult(
        video_format=VIDEO_FORMAT_SHORTS,
        video_orientation=VIDEO_ORIENTATION_MOBILE,
        aspect_ratio_hint="9:16",
        source="yt_dlp_probe",
        width=1080,
        height=1920,
        duration_sec=42.0,
        title="Example Short",
    )

    merged = merge_format_detection_results(url_result, probe_result)

    assert merged.video_orientation == VIDEO_ORIENTATION_MOBILE
    assert merged.duration_sec == 42.0
    assert merged.width == 1080
    assert merged.height == 1920
    assert merged.title == "Example Short"


def test_detect_video_format_from_url_landscape():
    result = detect_video_format_from_url("https://www.youtube.com/watch?v=abc123")
    assert result.video_orientation == VIDEO_ORIENTATION_LANDSCAPE
