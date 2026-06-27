from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.config import get_settings
from app.constants.video_sources import detect_platform_name, is_downloadable_platform_url
from app.schemas import CandidateVideo
from app.services.web_video_fetch import DownloadAttemptResult, WebVideoFetchService


class PlatformVideoDownloadAgent(BaseAgent):
    agent_id = "platform_video_download"
    agent_name = "Video Download"

    def __init__(self, target: str = "pool") -> None:
        self.target = target

    def _find_candidate(self, blackboard: ProjectBlackboard, candidate_id: str) -> CandidateVideo | None:
        for candidate in blackboard.candidate_pool:
            if candidate.candidate_id == candidate_id:
                return candidate
        for candidate in blackboard.selected_candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        for candidate in blackboard.approved_candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        return None

    async def download_single_candidate(
        self,
        blackboard: ProjectBlackboard,
        candidate: CandidateVideo,
    ) -> DownloadAttemptResult | None:
        settings = get_settings()
        if not settings.allow_web_video_fetch:
            self.record_download_event(
                blackboard,
                concept=candidate.concept,
                stage="skipped",
                candidate_id=candidate.candidate_id,
                error="ALLOW_WEB_VIDEO_FETCH=false",
            )
            return None

        if candidate.local_file_path:
            self.record_download_event(
                blackboard,
                concept=candidate.concept,
                stage="skipped",
                candidate_id=candidate.candidate_id,
                local_file_path=candidate.local_file_path,
                metadata={"reason": "already_downloaded"},
            )
            return None

        if not candidate.source_url or not is_downloadable_platform_url(candidate.source_url):
            self.record_download_event(
                blackboard,
                concept=candidate.concept,
                stage="download_failed",
                candidate_id=candidate.candidate_id,
                error="No supported source URL",
            )
            return DownloadAttemptResult(
                success=False,
                source_url=candidate.source_url,
                error="No supported source URL",
            )

        fetch_service = WebVideoFetchService()
        platform = detect_platform_name(candidate.source_url)

        self.record_download_event(
            blackboard,
            concept=candidate.concept,
            stage="download_started",
            candidate_id=candidate.candidate_id,
            platform=platform,
            source_url=candidate.source_url,
            metadata={"method": "yt-dlp", "trigger": "approval"},
        )

        result = await fetch_service.download_platform_url(
            project_id=blackboard.project_id,
            page_url=candidate.source_url,
            concept=candidate.concept,
        )

        if result.success and result.local_file_path:
            candidate.local_file_path = result.local_file_path
            candidate.source_type = result.source_type
            candidate.reason = f"Downloaded from {platform}"
            candidate.source_safety_score = 0.75
            candidate.visual_quality_score = max(candidate.visual_quality_score, 0.65)
            self.record_download_event(
                blackboard,
                concept=candidate.concept,
                stage="download_success",
                candidate_id=candidate.candidate_id,
                platform=result.platform,
                source_url=result.source_url,
                local_file_path=result.local_file_path,
                file_size_bytes=result.file_size_bytes,
                metadata={"method": result.method, "trigger": "approval"},
            )
            return result

        candidate.source_safety_score = 0.3
        candidate.reason = result.error or "Download failed — URL still usable"
        self.record_download_event(
            blackboard,
            concept=candidate.concept,
            stage="download_failed",
            candidate_id=candidate.candidate_id,
            platform=platform,
            source_url=candidate.source_url,
            error=result.error,
            metadata={"stderr": (result.stderr or "")[:500], "method": result.method},
        )
        return result

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        trace = self.active_trace(blackboard)
        trace.input_summary = "On-demand download"
        trace.output_summary = "Skipped — videos download one at a time when approved"
        trace.visible_reasoning = "Each approved candidate triggers its own download."
        return blackboard
