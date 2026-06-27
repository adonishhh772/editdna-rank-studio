import asyncio

from app.agents.candidate_discovery_agent import CandidateDiscoveryAgent
from app.db import create_project, new_id
from app.schemas import AgentTrace, ReferenceBlueprint, TopicResearch


def test_candidate_discovery_prepares_concepts_for_review():
    blackboard = create_project("test-user", "Discovery Limit Test")
    blackboard.reference_blueprint = ReferenceBlueprint(
        blueprint_id=new_id("bp"),
        project_id=blackboard.project_id,
        video_type="ranking_video",
        ranking_count=5,
        ranking_order="5_to_1",
        hook_duration_sec=3.0,
        average_item_duration_sec=4.0,
        outro_duration_sec=2.0,
        duration_sec=30.0,
        aspect_ratio="9:16",
        hook_style="question",
        rank_reveal_style="countdown",
        final_rank_drama_level="medium",
        confidence=0.9,
        section_order=[],
        caption_style={},
        text_overlay_style={},
        transition_style={},
        audio_style={},
        motion_style={},
        pacing_style={},
    )
    blackboard.topic_research = TopicResearch(
        project_id=blackboard.project_id,
        topic="AI tools",
        ranking_count=5,
        research_summary="Test research",
        candidate_concepts=[f"Concept {index}" for index in range(1, 12)],
        source_urls=[],
        search_results=[],
    )
    blackboard.topic = "AI tools"

    agent = CandidateDiscoveryAgent()
    blackboard.traces.append(
        AgentTrace(
            trace_id=new_id("trace"),
            project_id=blackboard.project_id,
            run_id=blackboard.run_id,
            agent_id=agent.agent_id,
            agent_name=agent.agent_name,
            status="running",
        )
    )

    result = asyncio.run(agent.run(blackboard))
    assert result.stage == "concepts_discovered"
    assert len(result.candidate_pool) == 0
    assert len(result.candidate_review_queue) == 5
    assert result.review_active is True
    assert result.candidate_review_queue[0].concept == "Concept 1"
    assert "5 concepts" in result.traces[-1].output_summary
