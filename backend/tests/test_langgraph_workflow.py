import pytest

from app.agents.workflow.graphs import build_full_pipeline_graph, build_stage_graphs
from app.agents.workflow.runner import LangGraphRunner
from app.blackboard import ProjectBlackboard
from app.constants.workflow import (
    STAGE_ANALYSE_REFERENCE,
    STAGE_COMPARE,
    STAGE_CREATE_EDIT_PLAN,
    STAGE_DISCOVER_CANDIDATES,
    STAGE_FEEDBACK,
    STAGE_REGENERATE,
    STAGE_RENDER,
    STAGE_RESEARCH_TOPIC,
    STAGE_SELECT_RANKING,
)
from app.schemas import CandidateVideo


def _minimal_candidate(project_id: str, rank: int = 1) -> CandidateVideo:
    return CandidateVideo(
        candidate_id=f"cand-{rank}",
        project_id=project_id,
        title="Clip",
        source_type="sample_asset",
        concept="Demo",
        topic_match_score=0.8,
        visual_quality_score=0.8,
        audio_quality_score=0.7,
        motion_energy_score=0.7,
        text_relevance_score=0.7,
        reference_style_fit_score=0.7,
        source_safety_score=1.0,
        overall_score=0.75,
        recommended_rank=rank,
        reason="Test candidate",
        local_file_path="/tmp/clip.mp4",
        duration_sec=5.0,
    )


def test_stage_graphs_include_all_pipeline_stages() -> None:
    graphs = build_stage_graphs()
    expected_stages = {
        STAGE_ANALYSE_REFERENCE,
        STAGE_RESEARCH_TOPIC,
        STAGE_DISCOVER_CANDIDATES,
        STAGE_SELECT_RANKING,
        STAGE_CREATE_EDIT_PLAN,
        STAGE_RENDER,
        STAGE_COMPARE,
        STAGE_FEEDBACK,
        STAGE_REGENERATE,
    }
    assert set(graphs.keys()) == expected_stages


def test_full_pipeline_graph_compiles() -> None:
    graph = build_full_pipeline_graph()
    assert graph.name == "full_pipeline"


def test_validate_candidates_node_rejects_empty_pool() -> None:
    import asyncio

    from app.agents.workflow.nodes import validate_candidates_node

    board = ProjectBlackboard(
        project_id="proj-test",
        run_id="run-test",
        user_id="user-test",
    )

    with pytest.raises(RuntimeError, match="No candidates available"):
        asyncio.run(validate_candidates_node({"blackboard": board}))


def test_validate_candidates_node_accepts_selected_candidates() -> None:
    import asyncio

    from app.agents.workflow.nodes import validate_candidates_node

    board = ProjectBlackboard(
        project_id="proj-test",
        run_id="run-test",
        user_id="user-test",
        selected_candidates=[_minimal_candidate("proj-test")],
    )

    result = asyncio.run(validate_candidates_node({"blackboard": board}))
    assert result["blackboard"].project_id == "proj-test"


@pytest.mark.asyncio
async def test_runner_clear_human_gate() -> None:
    runner = LangGraphRunner()
    board = ProjectBlackboard(
        project_id="proj-gate",
        run_id="run-gate",
        user_id="user-gate",
        waiting_for_human=True,
        human_gate_type="edit_plan_approval",
    )
    updated = await runner.clear_human_gate(board)
    assert updated.waiting_for_human is False
    assert updated.human_gate_type is None


def test_apply_fusion_to_sections_builds_ranked_clips() -> None:
    from app.agents.workflow.nodes import apply_fusion_to_sections

    board = ProjectBlackboard(
        project_id="proj-fusion",
        run_id="run-fusion",
        user_id="user-fusion",
        topic="Top demos",
    )
    candidates = [_minimal_candidate("proj-fusion")]
    hook, outro, sections, captions, motion, transitions = apply_fusion_to_sections(
        board,
        candidates,
        4.0,
    )
    assert "Top 1" in hook
    assert outro
    assert len(sections) == 1
    assert sections[0].rank == 1
    assert len(captions) == 1
    assert len(motion) == 1
    assert len(transitions) == 1
