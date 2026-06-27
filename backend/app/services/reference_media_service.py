from pathlib import Path

from app.config import get_settings
from app.services.web_video_fetch import WebVideoFetchService


async def ensure_reference_local_path(
    project_id: str,
    reference_video_path: str | None,
    reference_video_url: str | None,
) -> str | None:
    if reference_video_path:
        local_path = Path(reference_video_path)
        if local_path.exists():
            return str(local_path)

    if not reference_video_url:
        return None

    settings = get_settings()
    if not settings.allow_web_video_fetch:
        return None

    fetch_service = WebVideoFetchService()
    download_result = await fetch_service.download_video_url(
        project_id=project_id,
        video_url=reference_video_url,
        concept="reference",
        subdir="reference",
    )
    if download_result.success and download_result.local_file_path:
        return download_result.local_file_path
    return None
