import asyncio
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.constants.video_sources import (
    MAX_DOWNLOAD_BYTES,
    MAX_PLATFORM_SEARCHES_PER_CONCEPT,
    MAX_SEARCH_RESULTS_PER_QUERY,
    VIDEO_URL_EXTENSIONS,
    YOUTUBE_SEARCH_MODE_SHORTS,
    detect_platform_name,
    is_downloadable_platform_url,
    is_single_tiktok_video_url,
    is_single_youtube_video_url,
    platform_download_priority,
)
from app.integrations.tavily_client import TavilyResearchClient
from app.schemas import ReferenceBlueprint
from app.services.candidate_preference_service import (
    preference_blocked_orientations,
    preference_max_duration_sec,
)
from app.services.preference_learning_service import compute_preference_learning_adjustment
from app.services.video_constraint_service import ReferenceVideoConstraints, evaluate_video_fit
from app.services.video_format_detection import probe_platform_video_metadata
from app.services.ytdlp_command import build_ytdlp_download_args, impersonation_available


@dataclass
class PlatformSearchHit:
    url: str
    title: str
    platform: str
    search_query: str
    score: float = 0.0
    duration_sec: float | None = None
    width: int | None = None
    height: int | None = None
    fit_score: float = 0.0
    orientation: str | None = None
    aspect_ratio_hint: str | None = None
    learning_reasons: list[str] = field(default_factory=list)


@dataclass
class DownloadAttemptResult:
    success: bool
    local_file_path: str | None = None
    source_url: str | None = None
    source_type: str = "public_url_reference"
    title: str = ""
    reason: str = ""
    platform: str | None = None
    file_size_bytes: int | None = None
    error: str | None = None
    stderr: str | None = None
    method: str = "yt-dlp"


class WebVideoFetchService:
    VIDEO_URL_PATTERN = re.compile(
        r"https?://[^\s\"'<>]+?(?:\.(?:mp4|webm|mov|mkv)|/video/[^\s\"'<>]+)(?:\?[^\s\"'<>]*)?",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self.settings = get_settings()

    async def search_platform_urls(
        self,
        concept: str,
        topic: str,
        max_queries: int = MAX_PLATFORM_SEARCHES_PER_CONCEPT,
        exclude_urls: set[str] | None = None,
        youtube_search_mode: str | None = None,
        constraints: ReferenceVideoConstraints | None = None,
        memory_context: dict[str, Any] | None = None,
    ) -> list[PlatformSearchHit]:
        if not self.settings.allow_web_video_fetch:
            return []

        youtube_hits = await self.search_youtube_hits(
            concept=concept,
            topic=topic,
            exclude_urls=exclude_urls,
            youtube_search_mode=youtube_search_mode,
            constraints=constraints,
            memory_context=memory_context,
        )
        prefer_shorts = youtube_search_mode in {YOUTUBE_SEARCH_MODE_SHORTS, "shorts", None}
        tiktok_hits: list[PlatformSearchHit] = []
        if prefer_shorts:
            tiktok_hits = await self.search_tiktok_hits(
                concept=concept,
                topic=topic,
                exclude_urls=exclude_urls,
                constraints=constraints,
                memory_context=memory_context,
            )

        merged = youtube_hits + tiktok_hits
        merged.sort(key=lambda hit: (platform_download_priority(hit.url), -hit.fit_score, -hit.score))
        return merged[: max_queries * MAX_SEARCH_RESULTS_PER_QUERY]

    async def search_youtube_hits(
        self,
        *,
        concept: str,
        topic: str,
        exclude_urls: set[str] | None = None,
        youtube_search_mode: str | None = None,
        constraints: ReferenceVideoConstraints | None = None,
        memory_context: dict[str, Any] | None = None,
    ) -> list[PlatformSearchHit]:
        if not self.settings.allow_web_video_fetch:
            return []

        blocked_urls = exclude_urls or set()
        tavily = TavilyResearchClient()
        hits: list[PlatformSearchHit] = []
        seen_urls: set[str] = set()
        context = memory_context or {}

        results = await tavily.search_youtube_video_urls(
            concept,
            topic,
            search_mode=youtube_search_mode,
        )
        for item in results:
            hit = await self._build_hit_from_search_item(
                item=item,
                concept=concept,
                topic=topic,
                seen_urls=seen_urls,
                blocked_urls=blocked_urls,
                url_validator=is_single_youtube_video_url,
                constraints=constraints,
                memory_context=context,
            )
            if hit is not None:
                hits.append(hit)

        hits.sort(key=lambda candidate: (-candidate.fit_score, -candidate.score))
        return hits

    async def search_tiktok_hits(
        self,
        *,
        concept: str,
        topic: str,
        exclude_urls: set[str] | None = None,
        constraints: ReferenceVideoConstraints | None = None,
        memory_context: dict[str, Any] | None = None,
    ) -> list[PlatformSearchHit]:
        if not self.settings.allow_web_video_fetch:
            return []

        blocked_urls = exclude_urls or set()
        tavily = TavilyResearchClient()
        hits: list[PlatformSearchHit] = []
        seen_urls: set[str] = set()
        context = memory_context or {}

        results = await tavily.search_tiktok_video_urls(concept, topic)
        for item in results:
            hit = await self._build_hit_from_search_item(
                item=item,
                concept=concept,
                topic=topic,
                seen_urls=seen_urls,
                blocked_urls=blocked_urls,
                url_validator=is_single_tiktok_video_url,
                constraints=constraints,
                memory_context=context,
            )
            if hit is not None:
                hits.append(hit)

        hits.sort(key=lambda candidate: (-candidate.fit_score, -candidate.score))
        return hits

    @staticmethod
    def merge_search_hit_dicts(
        *,
        youtube_hits: list[dict[str, Any]],
        tiktok_hits: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged = youtube_hits + tiktok_hits
        merged.sort(
            key=lambda hit: (
                platform_download_priority(str(hit.get("url") or "")),
                -float(hit.get("fit_score") or 0.0),
                -float(hit.get("score") or 0.0),
            )
        )
        return merged

    @staticmethod
    def hits_from_dicts(raw_hits: list[dict[str, Any]]) -> list[PlatformSearchHit]:
        return [PlatformSearchHit(**item) for item in raw_hits]

    async def _build_hit_from_search_item(
        self,
        *,
        item: dict[str, Any],
        concept: str,
        topic: str,
        seen_urls: set[str],
        blocked_urls: set[str],
        url_validator,
        constraints: ReferenceVideoConstraints | None,
        memory_context: dict[str, Any],
    ) -> PlatformSearchHit | None:
        url = item.get("url", "")
        if not url or url in seen_urls or url in blocked_urls:
            return None
        if not is_downloadable_platform_url(url) or not url_validator(url):
            return None
        seen_urls.add(url)

        probe = await probe_platform_video_metadata(url)
        pref_max_duration = preference_max_duration_sec(memory_context)
        blocked_orientations = preference_blocked_orientations(memory_context)

        fit_score = float(item.get("score", 0.0) or 0.0)
        if constraints is not None:
            evaluation = evaluate_video_fit(
                duration_sec=probe.duration_sec,
                width=probe.width,
                height=probe.height,
                orientation=probe.video_orientation,
                aspect_ratio_hint=probe.aspect_ratio_hint,
                constraints=constraints,
                preference_max_duration_sec=pref_max_duration,
                blocked_orientations=blocked_orientations,
            )
            if not evaluation.acceptable:
                return None
            fit_score = evaluation.fit_score

        preference_delta, learning_reasons = compute_preference_learning_adjustment(
            duration_sec=probe.duration_sec,
            orientation=probe.video_orientation,
            aspect_ratio_hint=probe.aspect_ratio_hint,
            memory_context=memory_context,
            target_duration_sec=(
                constraints.target_candidate_duration_sec if constraints else None
            ),
        )
        fit_score = max(min(fit_score + preference_delta, 1.0), 0.0)

        return PlatformSearchHit(
            url=url,
            title=probe.title or item.get("title", concept)[:120],
            platform=detect_platform_name(url),
            search_query=f"{concept} {topic}",
            score=float(item.get("score", 0.0) or 0.0),
            duration_sec=probe.duration_sec,
            width=probe.width,
            height=probe.height,
            fit_score=fit_score,
            orientation=probe.video_orientation,
            aspect_ratio_hint=probe.aspect_ratio_hint,
            learning_reasons=learning_reasons,
        )

    @staticmethod
    def build_constraints_from_blueprint(
        blueprint: ReferenceBlueprint | None,
    ) -> ReferenceVideoConstraints | None:
        if blueprint is None:
            return None
        return ReferenceVideoConstraints.from_blueprint(blueprint)

    async def download_platform_url(
        self,
        project_id: str,
        page_url: str,
        concept: str,
        subdir: str = "candidates",
    ) -> DownloadAttemptResult:
        platform = detect_platform_name(page_url)
        if platform == "tiktok" and not impersonation_available():
            return DownloadAttemptResult(
                success=False,
                source_url=page_url,
                platform=platform,
                error=(
                    "TikTok downloads require curl-cffi for browser impersonation. "
                    "Install with: pip install 'curl-cffi>=0.10.0,<0.14'"
                ),
                method="yt-dlp",
            )
        local_path, stderr, error = await self._download_with_ytdlp(
            project_id=project_id,
            page_url=page_url,
            filename_hint=f"{platform}_{abs(hash(page_url)) % 100000}.mp4",
            subdir=subdir,
        )
        if not local_path:
            return DownloadAttemptResult(
                success=False,
                source_url=page_url,
                platform=platform,
                error=error or "yt-dlp download failed",
                stderr=stderr,
                method="yt-dlp",
            )

        file_size = Path(local_path).stat().st_size
        return DownloadAttemptResult(
            success=True,
            local_file_path=local_path,
            source_url=page_url,
            source_type="public_url_reference",
            title=concept[:120],
            reason=f"Downloaded from {platform} via yt-dlp",
            platform=platform,
            file_size_bytes=file_size,
            method="yt-dlp",
        )

    async def download_direct_url(
        self,
        project_id: str,
        download_url: str,
        concept: str,
        subdir: str = "candidates",
    ) -> DownloadAttemptResult:
        local_path, error = await self._download_direct_file(
            project_id=project_id,
            download_url=download_url,
            filename_hint=f"direct_{abs(hash(download_url)) % 100000}.mp4",
            subdir=subdir,
        )
        if not local_path:
            return DownloadAttemptResult(
                success=False,
                source_url=download_url,
                platform="direct",
                error=error or "Direct download failed",
                method="http",
            )
        return DownloadAttemptResult(
            success=True,
            local_file_path=local_path,
            source_url=download_url,
            source_type="public_url_reference",
            title=concept[:120],
            reason="Downloaded direct media URL",
            platform="direct",
            file_size_bytes=Path(local_path).stat().st_size,
            method="http",
        )

    async def discover_direct_urls_on_page(self, page_url: str) -> list[str]:
        tavily = TavilyResearchClient()
        extracted_pages = await tavily.extract_source_context([page_url])
        discovered: list[str] = []
        for page in extracted_pages:
            raw_content = page.get("raw_content") or ""
            for match in self.VIDEO_URL_PATTERN.findall(raw_content):
                if self._is_direct_video_url(match):
                    discovered.append(match)
        return discovered

    def _is_direct_video_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        return parsed.path.lower().endswith(VIDEO_URL_EXTENSIONS)

    async def download_video_url(
        self,
        project_id: str,
        video_url: str,
        concept: str,
        subdir: str = "candidates",
    ) -> DownloadAttemptResult:
        if is_downloadable_platform_url(video_url):
            return await self.download_platform_url(
                project_id=project_id,
                page_url=video_url,
                concept=concept,
                subdir=subdir,
            )
        return await self.download_direct_url(
            project_id=project_id,
            download_url=video_url,
            concept=concept,
            subdir=subdir,
        )

    async def _download_with_ytdlp(
        self,
        project_id: str,
        page_url: str,
        filename_hint: str,
        subdir: str = "candidates",
    ) -> tuple[str | None, str | None, str | None]:
        candidate_dir = self.settings.upload_dir / project_id / subdir
        candidate_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(candidate_dir / filename_hint.replace(".mp4", ".%(ext)s"))
        self._cleanup_stale_part_files(candidate_dir, Path(filename_hint).stem)

        def run_ytdlp() -> tuple[str | None, str | None, str | None]:
            command = build_ytdlp_download_args(output_template, page_url)
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return None, result.stderr, result.stderr[-500:] if result.stderr else "yt-dlp failed"

            stem = Path(filename_hint).stem
            for candidate_file in candidate_dir.glob(f"{stem}.*"):
                if candidate_file.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}:
                    if candidate_file.stat().st_size >= 50_000:
                        return str(candidate_file), result.stderr, None
            return None, result.stderr, "No output file produced"

        return await asyncio.to_thread(run_ytdlp)

    @staticmethod
    def _cleanup_stale_part_files(candidate_dir: Path, filename_stem: str) -> None:
        for stale_part in candidate_dir.glob(f"{filename_stem}*.part"):
            stale_part.unlink(missing_ok=True)

    async def _download_direct_file(
        self,
        project_id: str,
        download_url: str,
        filename_hint: str,
        subdir: str = "candidates",
    ) -> tuple[str | None, str | None]:
        candidate_dir = self.settings.upload_dir / project_id / subdir
        candidate_dir.mkdir(parents=True, exist_ok=True)
        target_path = candidate_dir / filename_hint

        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                async with client.stream("GET", download_url) as response:
                    if response.status_code >= 400:
                        return None, f"HTTP {response.status_code}"
                    total_bytes = 0
                    chunks: list[bytes] = []
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        total_bytes += len(chunk)
                        if total_bytes > MAX_DOWNLOAD_BYTES:
                            return None, "File exceeds max download size"
                        chunks.append(chunk)
            if total_bytes < 50_000:
                return None, "File too small"
            target_path.write_bytes(b"".join(chunks))
            return str(target_path), None
        except Exception as exc:
            return None, str(exc)
