from typing import Any

from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.constants.video_sources import YOUTUBE_SEARCH_MODE_SHORTS
from app.services.video_constraint_service import ReferenceVideoConstraints
from app.services.web_video_fetch import WebVideoFetchService


def resolve_search_constraints(
    blackboard: ProjectBlackboard,
    request: dict[str, Any],
) -> ReferenceVideoConstraints | None:
    blueprint_constraints = WebVideoFetchService.build_constraints_from_blueprint(blackboard.reference_blueprint)
    if blueprint_constraints is None:
        return None
    search_mode = request.get("youtube_search_mode")
    return blueprint_constraints.for_platform_search(search_mode)


class YouTubeShortsSearchAgent(BaseAgent):
    agent_id = "youtube_shorts_search"
    agent_name = "Tavily YouTube Search"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        request = blackboard.memory_context.get("_platform_search_request", {})
        concept = str(request.get("concept") or "")
        topic = str(request.get("topic") or "")
        search_mode = request.get("youtube_search_mode")
        constraints = resolve_search_constraints(blackboard, request)

        fetch_service = WebVideoFetchService()
        hits = await fetch_service.search_youtube_hits(
            concept=concept,
            topic=topic,
            exclude_urls=set(request.get("exclude_urls") or []),
            youtube_search_mode=search_mode,
            constraints=constraints,
            memory_context=blackboard.memory_context,
        )

        blackboard.memory_context["_youtube_search_hits"] = [hit.__dict__ for hit in hits]
        trace = self.active_trace(blackboard)
        trace.input_summary = f"YouTube search for '{concept}' ({search_mode or 'any'} mode)"
        trace.output_summary = f"Found {len(hits)} YouTube hits"
        trace.visible_reasoning = (
            f"Probed {len(hits)} YouTube Shorts/video URLs matching ~"
            f"{constraints.target_candidate_duration_sec:.0f}s reference"
            if constraints and hits
            else f"Found {len(hits)} YouTube URLs for '{concept}'"
        )
        self.record_download_event(
            blackboard,
            concept=concept,
            stage="search_started",
            platform="youtube",
            search_query=f"{concept} {topic}",
            metadata={"hit_count": len(hits), "search_mode": search_mode},
        )
        if hits:
            best = hits[0]
            self.record_download_event(
                blackboard,
                concept=concept,
                stage="url_selected",
                platform=best.platform,
                source_url=best.url,
                search_query=best.search_query,
                metadata={"fit_score": best.fit_score, "learning_reasons": best.learning_reasons},
            )
        return blackboard


class TikTokSearchAgent(BaseAgent):
    agent_id = "tiktok_search"
    agent_name = "TikTok Search"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        request = blackboard.memory_context.get("_platform_search_request", {})
        concept = str(request.get("concept") or "")
        topic = str(request.get("topic") or "")
        constraints = resolve_search_constraints(blackboard, request)

        fetch_service = WebVideoFetchService()
        hits = await fetch_service.search_tiktok_hits(
            concept=concept,
            topic=topic,
            exclude_urls=set(request.get("exclude_urls") or []),
            constraints=constraints,
            memory_context=blackboard.memory_context,
        )

        blackboard.memory_context["_tiktok_search_hits"] = [hit.__dict__ for hit in hits]
        trace = self.active_trace(blackboard)
        trace.input_summary = f"TikTok search for '{concept}'"
        trace.output_summary = f"Found {len(hits)} TikTok hits"
        trace.visible_reasoning = (
            f"Found {len(hits)} raw TikTok clips related to '{concept}'"
        )
        self.record_download_event(
            blackboard,
            concept=concept,
            stage="search_started",
            platform="tiktok",
            search_query=f"{concept} {topic} tiktok",
            metadata={"hit_count": len(hits)},
        )
        if hits:
            best = hits[0]
            self.record_download_event(
                blackboard,
                concept=concept,
                stage="url_selected",
                platform="tiktok",
                source_url=best.url,
                search_query=best.search_query,
                metadata={"fit_score": best.fit_score},
            )
        return blackboard


class PlatformSearchSwarmAgent(BaseAgent):
    agent_id = "platform_search_swarm"
    agent_name = "Platform Search Swarm"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        request = blackboard.memory_context.get("_platform_search_request", {})
        concept = str(request.get("concept") or "")
        search_mode = request.get("youtube_search_mode")
        prefer_shorts = search_mode in {YOUTUBE_SEARCH_MODE_SHORTS, "shorts", None}

        parent_trace = self.active_trace(blackboard)
        parent_agent_id = self.agent_id

        youtube_agent = YouTubeShortsSearchAgent()
        blackboard = await youtube_agent.execute(
            blackboard,
            parent_agent_id=parent_agent_id,
            swarm=True,
        )

        sub_agents = [YouTubeShortsSearchAgent.agent_id]
        if prefer_shorts:
            tiktok_agent = TikTokSearchAgent()
            blackboard = await tiktok_agent.execute(
                blackboard,
                parent_agent_id=parent_agent_id,
                swarm=True,
            )
            sub_agents.append(TikTokSearchAgent.agent_id)

        fetch_service = WebVideoFetchService()
        merged_hits = fetch_service.merge_search_hit_dicts(
            youtube_hits=blackboard.memory_context.pop("_youtube_search_hits", []),
            tiktok_hits=blackboard.memory_context.pop("_tiktok_search_hits", []),
        )
        blackboard.memory_context["_platform_search_merged_hits"] = merged_hits

        parent_trace.input_summary = f"Swarm search for slot concept '{concept}'"
        parent_trace.output_summary = f"Merged {len(merged_hits)} platform hits"
        parent_trace.visible_reasoning = (
            "YouTube + TikTok swarm searched for raw vertical clips matching reference format."
            if prefer_shorts
            else "YouTube swarm searched for clips matching reference format."
        )
        parent_trace.metadata["sub_agents"] = sub_agents
        parent_trace.metadata["swarm"] = True
        parent_trace.metadata["prefer_shorts"] = prefer_shorts
        return blackboard
