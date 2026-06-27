from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.config import get_settings
from app.constants.video_sources import DEFAULT_RANKING_COUNT
from app.services.web_video_fetch import WebVideoFetchService


class PlatformVideoSearchAgent(BaseAgent):
    agent_id = "platform_video_search"
    agent_name = "Video Search"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        settings = get_settings()
        if not settings.allow_web_video_fetch:
            self.active_trace(blackboard).visible_reasoning = "Web fetch disabled"
            self.record_download_event(
                blackboard,
                concept="all",
                stage="skipped",
                error="ALLOW_WEB_VIDEO_FETCH=false",
            )
            return blackboard

        fetch_service = WebVideoFetchService()
        topic = blackboard.topic or ""
        ranking_count = (
            blackboard.reference_blueprint.ranking_count
            if blackboard.reference_blueprint
            else DEFAULT_RANKING_COUNT
        )
        youtube_search_mode = (
            blackboard.topic_research.youtube_search_mode if blackboard.topic_research else None
        )
        web_candidates = [
            candidate
            for candidate in blackboard.candidate_pool
            if not candidate.local_file_path
        ][:ranking_count]

        url_count = 0
        for candidate in web_candidates:
            self.record_download_event(
                blackboard,
                concept=candidate.concept,
                stage="search_started",
                candidate_id=candidate.candidate_id,
                search_query=f"{candidate.concept} {topic}",
            )

            hits = await fetch_service.search_platform_urls(
                candidate.concept,
                topic,
                youtube_search_mode=youtube_search_mode,
                constraints=WebVideoFetchService.build_constraints_from_blueprint(blackboard.reference_blueprint),
                memory_context=blackboard.memory_context,
            )
            if hits:
                best_hit = hits[0]
                candidate.source_url = best_hit.url
                candidate.title = best_hit.title
                candidate.source_type = "public_url_reference"
                url_count += 1
                self.record_download_event(
                    blackboard,
                    concept=candidate.concept,
                    stage="url_selected",
                    candidate_id=candidate.candidate_id,
                    platform=best_hit.platform,
                    search_query=best_hit.search_query,
                    source_url=best_hit.url,
                    metadata={"title": best_hit.title, "score": best_hit.score},
                )
            else:
                candidate.reason = f"No YouTube URL found for '{candidate.concept}'"

        trace = self.active_trace(blackboard)
        trace.input_summary = f"Searching {len(web_candidates)} concepts on YouTube"
        trace.output_summary = f"Found URLs for {url_count}/{len(web_candidates)} candidates"
        trace.visible_reasoning = (
            f"Tavily search per concept ({youtube_search_mode or 'any'} YouTube mode). "
            "Download happens when you approve each candidate."
        )
        blackboard.stage = "platform_urls_discovered"
        return blackboard
