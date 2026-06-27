from app.agents.base import BaseAgent
from app.agents.reference_format_detection_agent import ReferenceFormatDetectionAgent
from app.agents.tavily_deep_research_agent import TavilyDeepResearchAgent
from app.agents.tavily_topic_search_agent import TavilyTopicSearchAgent
from app.blackboard import ProjectBlackboard
from app.constants.video_sources import (
    VIDEO_FORMAT_UNKNOWN,
    VIDEO_ORIENTATION_UNKNOWN,
    YOUTUBE_SEARCH_MODE_ANY,
    resolve_youtube_search_mode,
)
from app.integrations.tavily_client import TavilyResearchClient
from app.services.video_constraint_service import ReferenceVideoConstraints, constraints_summary
from app.services.video_format_detection import (
    detect_video_format_from_blueprint,
    detect_video_format_from_url,
    merge_format_detection_results,
)


class TavilyResearchAgent(BaseAgent):
    """Orchestrates research swarm: format detection, web search, and deep research."""

    agent_id = "tavily_research"
    agent_name = "Tavily Research Agent"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        if not blackboard.topic:
            raise RuntimeError("Topic is required")

        parent_trace = self.active_trace(blackboard)
        ranking_count = blackboard.reference_blueprint.ranking_count if blackboard.reference_blueprint else 5
        parent_agent_id = self.agent_id

        format_agent = ReferenceFormatDetectionAgent()
        search_agent = TavilyTopicSearchAgent()
        deep_research_agent = TavilyDeepResearchAgent()

        has_reference_signal = bool(
            blackboard.reference_video_url
            or (blackboard.reference_blueprint and blackboard.reference_blueprint.aspect_ratio)
        )
        youtube_search_mode = YOUTUBE_SEARCH_MODE_ANY
        format_metadata: dict[str, str] = {}

        if has_reference_signal:
            blackboard = await format_agent.execute(
                blackboard,
                parent_agent_id=parent_agent_id,
                swarm=True,
            )
            format_trace = format_agent.active_trace(blackboard)
            format_metadata = format_trace.metadata.get("format_detection", {})
            youtube_search_mode = format_trace.metadata.get(
                "youtube_search_mode",
                YOUTUBE_SEARCH_MODE_ANY,
            )
        else:
            url_result = detect_video_format_from_url(blackboard.reference_video_url)
            blueprint_result = detect_video_format_from_blueprint(
                blackboard.reference_blueprint.aspect_ratio if blackboard.reference_blueprint else None
            )
            merged = merge_format_detection_results(url_result, blueprint_result)
            youtube_search_mode = resolve_youtube_search_mode(merged.video_orientation)
            format_metadata = {
                "video_format": merged.video_format,
                "video_orientation": merged.video_orientation,
                "aspect_ratio_hint": merged.aspect_ratio_hint,
                "source": merged.source,
            }

        blackboard = await search_agent.execute(
            blackboard,
            parent_agent_id=parent_agent_id,
            swarm=True,
        )
        blackboard = await deep_research_agent.execute(
            blackboard,
            parent_agent_id=parent_agent_id,
            swarm=True,
        )

        search_data = blackboard.memory_context.pop("tavily_search_data", {})
        research_data = blackboard.memory_context.pop("tavily_research_data", None)

        client = TavilyResearchClient()
        concepts = client.build_concepts_from_sources(
            search_data,
            research_data,
            ranking_count,
            topic=blackboard.topic or "",
        )
        source_urls = client.collect_source_urls_from_sources(search_data, research_data)

        summary_parts: list[str] = []
        if search_data.get("answer"):
            summary_parts.append(search_data["answer"])
        if research_data and research_data.get("content"):
            summary_parts.append(research_data["content"][:2000])

        video_format = format_metadata.get("video_format", VIDEO_FORMAT_UNKNOWN)
        video_orientation = format_metadata.get("video_orientation", VIDEO_ORIENTATION_UNKNOWN)
        aspect_ratio_hint = format_metadata.get("aspect_ratio_hint", "unknown")
        reference_constraints = (
            ReferenceVideoConstraints.from_blueprint(blackboard.reference_blueprint)
            if blackboard.reference_blueprint
            else None
        )

        blackboard.topic_research = client.build_topic_research(
            project_id=blackboard.project_id,
            topic=blackboard.topic,
            ranking_count=ranking_count,
            research_summary="\n\n".join(summary_parts) or f"Research completed for: {blackboard.topic}",
            candidate_concepts=concepts,
            source_urls=source_urls,
            search_results=search_data.get("results", []),
            youtube_search_mode=youtube_search_mode,
            reference_video_format=video_format if video_format in {"shorts", "regular"} else "unknown",
            reference_video_orientation=video_orientation
            if video_orientation in {"mobile", "landscape"}
            else "unknown",
            aspect_ratio_hint=aspect_ratio_hint,
            target_candidate_duration_sec=(
                reference_constraints.target_candidate_duration_sec if reference_constraints else None
            ),
            rank_segment_duration_sec=(
                reference_constraints.rank_segment_duration_sec if reference_constraints else None
            ),
            max_source_duration_sec=(
                reference_constraints.max_source_duration_sec if reference_constraints else None
            ),
            min_source_duration_sec=(
                reference_constraints.min_source_duration_sec if reference_constraints else None
            ),
        )
        blackboard.stage = "topic_researched"

        parent_trace.input_summary = f"Research swarm for topic: {blackboard.topic[:80]}"
        parent_trace.output_summary = (
            f"Found {len(concepts)} concepts from {len(source_urls)} sources "
            f"({video_orientation} / {youtube_search_mode} search)"
        )
        parent_trace.visible_reasoning = (
            "Swarm completed format detection, Tavily search, and deep research. "
            "See child agent traces for each step."
        )
        parent_trace.metadata["sub_agents"] = [
            agent_id
            for agent_id in [
                ReferenceFormatDetectionAgent.agent_id if has_reference_signal else None,
                TavilyTopicSearchAgent.agent_id,
                TavilyDeepResearchAgent.agent_id,
            ]
            if agent_id is not None
        ]
        parent_trace.metadata["swarm"] = True
        parent_trace.metadata["youtube_search_mode"] = youtube_search_mode
        if reference_constraints:
            parent_trace.metadata["video_constraints"] = constraints_summary(reference_constraints)
        return blackboard
