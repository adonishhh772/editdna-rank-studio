import asyncio
import json
import subprocess
from dataclasses import dataclass

from app.constants.video_sources import (
    VIDEO_FORMAT_REGULAR,
    VIDEO_FORMAT_SHORTS,
    VIDEO_FORMAT_UNKNOWN,
    VIDEO_ORIENTATION_LANDSCAPE,
    VIDEO_ORIENTATION_MOBILE,
    VIDEO_ORIENTATION_UNKNOWN,
    detect_video_orientation_from_dimensions,
    detect_video_orientation_from_url,
    detect_youtube_video_format,
    is_youtube_url,
)
from app.services.ytdlp_command import build_ytdlp_probe_args


@dataclass
class VideoFormatDetectionResult:
    video_format: str
    video_orientation: str
    aspect_ratio_hint: str
    source: str
    width: int | None = None
    height: int | None = None
    duration_sec: float | None = None
    title: str | None = None
    probe_error: str | None = None


def detect_video_format_from_url(url: str | None) -> VideoFormatDetectionResult:
    if not url:
        return VideoFormatDetectionResult(
            video_format=VIDEO_FORMAT_UNKNOWN,
            video_orientation=VIDEO_ORIENTATION_UNKNOWN,
            aspect_ratio_hint="unknown",
            source="none",
        )

    video_format = detect_youtube_video_format(url)
    video_orientation = detect_video_orientation_from_url(url)
    aspect_ratio_hint = _orientation_to_aspect_ratio(video_orientation)

    return VideoFormatDetectionResult(
        video_format=video_format,
        video_orientation=video_orientation,
        aspect_ratio_hint=aspect_ratio_hint,
        source="url_heuristic",
    )


def detect_video_format_from_blueprint(aspect_ratio: str | None) -> VideoFormatDetectionResult | None:
    if not aspect_ratio:
        return None

    normalized = aspect_ratio.strip()
    if normalized == "9:16":
        return VideoFormatDetectionResult(
            video_format=VIDEO_FORMAT_SHORTS,
            video_orientation=VIDEO_ORIENTATION_MOBILE,
            aspect_ratio_hint="9:16",
            source="blueprint",
        )
    if normalized in {"16:9", "4:3", "21:9"}:
        return VideoFormatDetectionResult(
            video_format=VIDEO_FORMAT_REGULAR,
            video_orientation=VIDEO_ORIENTATION_LANDSCAPE,
            aspect_ratio_hint=normalized,
            source="blueprint",
        )
    return None


def merge_format_detection_results(
    primary: VideoFormatDetectionResult,
    secondary: VideoFormatDetectionResult | None,
) -> VideoFormatDetectionResult:
    if secondary is None:
        return primary

    merged_width = secondary.width or primary.width
    merged_height = secondary.height or primary.height
    merged_duration = (
        secondary.duration_sec if secondary.duration_sec is not None else primary.duration_sec
    )
    merged_title = secondary.title or primary.title
    merged_probe_error = secondary.probe_error or primary.probe_error
    merged_source = (
        f"{primary.source}+{secondary.source}"
        if secondary.source and secondary.source != primary.source
        else primary.source
    )

    if primary.video_orientation != VIDEO_ORIENTATION_UNKNOWN:
        return VideoFormatDetectionResult(
            video_format=primary.video_format,
            video_orientation=primary.video_orientation,
            aspect_ratio_hint=primary.aspect_ratio_hint,
            source=merged_source,
            width=merged_width,
            height=merged_height,
            duration_sec=merged_duration,
            title=merged_title,
            probe_error=merged_probe_error,
        )

    return VideoFormatDetectionResult(
        video_format=secondary.video_format
        if primary.video_format == VIDEO_FORMAT_UNKNOWN
        else primary.video_format,
        video_orientation=secondary.video_orientation,
        aspect_ratio_hint=secondary.aspect_ratio_hint
        if secondary.aspect_ratio_hint != "unknown"
        else primary.aspect_ratio_hint,
        source=merged_source,
        width=merged_width,
        height=merged_height,
        duration_sec=merged_duration,
        title=merged_title,
        probe_error=merged_probe_error,
    )


async def probe_youtube_video_metadata(url: str) -> VideoFormatDetectionResult:
    return await probe_platform_video_metadata(url)


async def probe_platform_video_metadata(url: str) -> VideoFormatDetectionResult:
    heuristic = detect_video_format_from_url(url)
    if not is_youtube_url(url) and "tiktok.com" not in url.lower():
        return heuristic

    def run_probe() -> VideoFormatDetectionResult:
        command = build_ytdlp_probe_args(url)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr_tail = (result.stderr or result.stdout or "yt-dlp probe failed")[-500:]
            return VideoFormatDetectionResult(
                video_format=heuristic.video_format,
                video_orientation=heuristic.video_orientation,
                aspect_ratio_hint=heuristic.aspect_ratio_hint,
                source="url_heuristic",
                probe_error=stderr_tail,
            )

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return heuristic

        width = payload.get("width")
        height = payload.get("height")
        duration = payload.get("duration")
        orientation = detect_video_orientation_from_dimensions(
            int(width) if isinstance(width, (int, float)) else None,
            int(height) if isinstance(height, (int, float)) else None,
        )
        if orientation == VIDEO_ORIENTATION_UNKNOWN:
            orientation = heuristic.video_orientation

        video_format = heuristic.video_format
        if video_format == VIDEO_FORMAT_UNKNOWN:
            if orientation == VIDEO_ORIENTATION_MOBILE:
                video_format = VIDEO_FORMAT_SHORTS
            elif orientation == VIDEO_ORIENTATION_LANDSCAPE:
                video_format = VIDEO_FORMAT_REGULAR

        return VideoFormatDetectionResult(
            video_format=video_format,
            video_orientation=orientation,
            aspect_ratio_hint=_orientation_to_aspect_ratio(orientation),
            source="yt_dlp_probe",
            width=int(width) if isinstance(width, (int, float)) else None,
            height=int(height) if isinstance(height, (int, float)) else None,
            duration_sec=float(duration) if isinstance(duration, (int, float)) else None,
            title=str(payload.get("title") or "")[:120] or None,
        )

    probe_result = await asyncio.to_thread(run_probe)
    return merge_format_detection_results(heuristic, probe_result)


def _orientation_to_aspect_ratio(video_orientation: str) -> str:
    if video_orientation == VIDEO_ORIENTATION_MOBILE:
        return "9:16"
    if video_orientation == VIDEO_ORIENTATION_LANDSCAPE:
        return "16:9"
    return "unknown"
