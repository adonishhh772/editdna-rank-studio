from dataclasses import dataclass
from typing import Any

from app.constants.video_sources import is_video_url
from app.integrations.slng_client import SLNGAudioClient
from app.services.reference_media_service import ensure_reference_local_path


@dataclass
class AudioAnalysisResult:
    audio_style: dict[str, Any]
    local_file_path: str | None = None


async def resolve_local_video_path(
    project_id: str,
    video_path: str | None = None,
    video_url: str | None = None,
    subdir: str = "reference",
) -> str | None:
    return await ensure_reference_local_path(
        project_id=project_id,
        reference_video_path=video_path,
        reference_video_url=video_url if is_video_url(video_url or "") else None,
    )


async def analyse_video_audio_style(
    project_id: str,
    video_path: str | None = None,
    video_url: str | None = None,
    subdir: str = "reference",
) -> AudioAnalysisResult | None:
    local_path = await resolve_local_video_path(
        project_id=project_id,
        video_path=video_path,
        video_url=video_url,
        subdir=subdir,
    )
    if not local_path:
        return None

    slng_client = SLNGAudioClient()
    audio_style = await slng_client.analyse_audio_style(local_path)
    cached_path = local_path if video_url and not video_path else None
    return AudioAnalysisResult(audio_style=audio_style, local_file_path=cached_path)
