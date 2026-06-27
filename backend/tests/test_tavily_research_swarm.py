from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.tavily_research_agent import TavilyResearchAgent
from app.db import create_project
from app.schemas import AgentTrace, ReferenceBlueprint, ReferenceSection


@pytest.fixture
def research_blackboard():
    blackboard = create_project("test-user", "Research Swarm Test")
    blackboard.topic = "embarrassing award moments"
    blackboard.reference_video_url = "https://www.youtube.com/shorts/uHSvwuEMdL0"
    blackboard.reference_blueprint = ReferenceBlueprint(
        blueprint_id="bp_test",
        project_id=blackboard.project_id,
        video_type="ranking_video",
        aspect_ratio="9:16",
        duration_sec=45.0,
        ranking_count=5,
        ranking_order="5_to_1",
        hook_duration_sec=3.0,
        average_item_duration_sec=4.0,
        outro_duration_sec=3.0,
        section_order=[
            ReferenceSection(
                name="hook",
                start_sec=0.0,
                end_sec=3.0,
                purpose="hook",
                visual_notes="",
                audio_notes="",
                text_notes="",
                motion_notes="",
            )
        ],
        caption_style={},
        text_overlay_style={},
        transition_style={},
        audio_style={},
        motion_style={},
        pacing_style={},
        hook_style="text_heavy",
        rank_reveal_style="countdown",
        final_rank_drama_level="high",
        confidence=0.9,
    )
    blackboard.traces.append(
        AgentTrace(
            trace_id="trace_parent",
            project_id=blackboard.project_id,
            run_id=blackboard.run_id,
            agent_id=TavilyResearchAgent.agent_id,
            agent_name=TavilyResearchAgent.agent_name,
            status="running",
        )
    )
    return blackboard


@pytest.mark.asyncio
async def test_tavily_research_swarm_records_child_traces(research_blackboard):
    agent = TavilyResearchAgent()

    with patch.object(
        agent,
        "active_trace",
        return_value=research_blackboard.traces[-1],
    ), patch(
        "app.agents.reference_format_detection_agent.probe_youtube_video_metadata",
        new_callable=AsyncMock,
    ) as mock_probe, patch(
        "app.agents.tavily_topic_search_agent.TavilyResearchClient"
    ) as mock_search_client_cls, patch(
        "app.agents.tavily_deep_research_agent.TavilyResearchClient"
    ) as mock_deep_client_cls, patch(
        "app.agents.tavily_research_agent.TavilyResearchClient"
    ) as mock_merge_client_cls:
        from app.services.video_format_detection import VideoFormatDetectionResult

        mock_probe.return_value = VideoFormatDetectionResult(
            video_format="shorts",
            video_orientation="mobile",
            aspect_ratio_hint="9:16",
            source="yt_dlp_probe",
            width=1080,
            height=1920,
        )

        search_client = MagicMock()
        search_client.search_topic_async = AsyncMock(
            return_value={"answer": "Found moments", "results": [{"title": "Trip on stage", "url": "https://x.com"}]}
        )
        mock_search_client_cls.return_value = search_client

        deep_client = MagicMock()
        deep_client.research_topic_focused_async = AsyncMock(
            return_value={"content": "1. Red carpet trip", "sources": []}
        )
        mock_deep_client_cls.return_value = deep_client

        merge_client = MagicMock()
        merge_client.build_concepts_from_sources.return_value = ["Red carpet trip"]
        merge_client.collect_source_urls_from_sources.return_value = ["https://x.com"]
        merge_client.build_topic_research.return_value = MagicMock()
        mock_merge_client_cls.return_value = merge_client

        result = await agent.run(research_blackboard)

        swarm_traces = [trace for trace in result.traces if trace.metadata.get("swarm")]
        assert len(swarm_traces) >= 3
        assert any(trace.agent_id == "reference_format_detection" for trace in swarm_traces)
        assert any(trace.agent_id == "tavily_topic_search" for trace in swarm_traces)
        assert any(trace.agent_id == "tavily_deep_research" for trace in swarm_traces)

        parent_trace = next(trace for trace in result.traces if trace.trace_id == "trace_parent")
        assert parent_trace.metadata.get("sub_agents")
        assert parent_trace.metadata.get("youtube_search_mode") == "shorts"
