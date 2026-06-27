import pytest

from app.agents.fusion_agent import FusionAgent
from app.agents.moe_bus import MoEBus, compute_routing_weights
from app.agents.story_agent import CaptionAgent, CutAgent, MotionAgent, StoryAgent
from app.blackboard import ProjectBlackboard
from app.schemas import AgentTrace, CandidateVideo, MoERoutingWeights, ReferenceBlueprint


def _sample_blueprint(project_id: str) -> ReferenceBlueprint:
    return ReferenceBlueprint(
        blueprint_id="bp-1",
        project_id=project_id,
        video_type="ranking_video",
        aspect_ratio="9:16",
        duration_sec=30.0,
        ranking_count=3,
        ranking_order="5_to_1",
        hook_duration_sec=2.0,
        average_item_duration_sec=4.0,
        outro_duration_sec=2.0,
        section_order=[],
        caption_style={"prominence": "high", "case": "upper"},
        text_overlay_style={},
        transition_style={},
        audio_style={},
        motion_style={"energy": "high"},
        pacing_style={"tempo": "fast"},
        hook_style="countdown",
        rank_reveal_style="dramatic",
        final_rank_drama_level="high",
        confidence=0.9,
    )


def _sample_candidates(project_id: str) -> list[CandidateVideo]:
    return [
        CandidateVideo(
            candidate_id="cand-1",
            project_id=project_id,
            title="Clip A",
            source_type="sample_asset",
            concept="Best demo reel",
            topic_match_score=0.9,
            visual_quality_score=0.8,
            audio_quality_score=0.7,
            motion_energy_score=0.85,
            text_relevance_score=0.8,
            reference_style_fit_score=0.75,
            source_safety_score=1.0,
            overall_score=0.85,
            recommended_rank=1,
            reason="Strong demo footage",
            local_file_path="/tmp/clip-a.mp4",
            duration_sec=6.0,
        ),
        CandidateVideo(
            candidate_id="cand-2",
            project_id=project_id,
            title="Clip B",
            source_type="sample_asset",
            concept="Runner up showcase",
            topic_match_score=0.8,
            visual_quality_score=0.75,
            audio_quality_score=0.7,
            motion_energy_score=0.6,
            text_relevance_score=0.7,
            reference_style_fit_score=0.7,
            source_safety_score=1.0,
            overall_score=0.72,
            recommended_rank=2,
            reason="Solid secondary pick",
            local_file_path="/tmp/clip-b.mp4",
            duration_sec=5.0,
        ),
    ]


def _sample_blackboard() -> ProjectBlackboard:
    board = ProjectBlackboard(
        project_id="proj-moe",
        run_id="run-moe",
        user_id="test-user",
        topic="AI Startups",
        reference_blueprint=_sample_blueprint("proj-moe"),
        approved_candidates=_sample_candidates("proj-moe"),
    )
    return board


@pytest.mark.anyio
async def test_compute_routing_weights_high_drama():
    board = _sample_blackboard()
    routing = compute_routing_weights(board, "round-1")

    assert routing.motion > routing.story
    assert abs(routing.story + routing.cut + routing.caption + routing.motion - 1.0) < 0.01
    assert "drama" in routing.reasoning.lower() or "Motion" in routing.reasoning


@pytest.mark.anyio
async def test_moe_pipeline_runs_experts_in_parallel():
    board = _sample_blackboard()
    moe_bus = MoEBus()
    experts = [StoryAgent(), CutAgent(), CaptionAgent(), MotionAgent()]

    result = await moe_bus.run_moe_pipeline(experts, board)

    assert len(result.expert_proposals) == 8
    assert len(result.agent_messages) >= 9
    assert result.moe_routing is not None

    domains = {proposal.domain for proposal in result.expert_proposals}
    assert domains == {"story", "cut", "caption", "motion"}


@pytest.mark.anyio
async def test_experts_exchange_peer_messages():
    board = _sample_blackboard()
    moe_bus = MoEBus()
    experts = [StoryAgent(), CutAgent(), CaptionAgent(), MotionAgent()]
    board = await moe_bus.run_moe_pipeline(experts, board)

    broadcast_messages = [message for message in board.agent_messages if message.to_agent_id is None]
    directed_messages = [message for message in board.agent_messages if message.to_agent_id is not None]

    assert len(broadcast_messages) >= 4
    assert len(directed_messages) >= 4

    cut_to_motion = [
        message
        for message in directed_messages
        if message.from_agent_id == "cut_agent" and message.to_agent_id == "motion_agent"
    ]
    assert len(cut_to_motion) >= 1


@pytest.mark.anyio
async def test_fusion_agent_merges_expert_proposals():
    board = _sample_blackboard()
    moe_bus = MoEBus()
    experts = [StoryAgent(), CutAgent(), CaptionAgent(), MotionAgent()]
    board = await moe_bus.run_moe_pipeline(experts, board)

    fusion_agent = FusionAgent()
    board.traces.append(
        AgentTrace(
            trace_id="trace-fusion",
            project_id=board.project_id,
            run_id=board.run_id,
            agent_id=fusion_agent.agent_id,
            agent_name=fusion_agent.agent_name,
            status="running",
        )
    )
    board = await fusion_agent.run(board)

    assert board.moe_fusion is not None
    assert board.moe_fusion.hook_text
    assert board.moe_fusion.outro_text
    assert len(board.moe_fusion.clip_adjustments) == 2
    assert len(board.moe_fusion.caption_updates) == 2
    assert any(item.get("zoom") for item in board.moe_fusion.motion_updates if item.get("rank") == 1)


@pytest.mark.anyio
async def test_story_agent_refines_from_cut_peer_messages():
    board = _sample_blackboard()
    story_agent = StoryAgent()
    cut_agent = CutAgent()
    routing = MoERoutingWeights(round_id="test", story=0.25, cut=0.25, caption=0.25, motion=0.25)

    _, cut_messages = await cut_agent.propose(board, "round-propose", [], routing)
    proposal, _ = await story_agent.propose(board, "round-refine", cut_messages, routing)

    assert proposal.outro_text
    assert "cut_agent" in proposal.peer_influence or len(cut_messages) > 0
