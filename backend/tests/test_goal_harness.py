from app.agents.workflow.nodes import route_after_critic
from app.agents.workflow.state import WorkflowState
from app.blackboard import ProjectBlackboard
from app.constants.harness import (
    GOAL_RANK_ONE_EMPHASIS,
    HARNESS_ROUTE_CONTINUE,
    HARNESS_ROUTE_RETRY,
    MAX_HARNESS_REVISIONS,
)
from app.schemas import (
    CandidateVideo,
    EditPlan,
    HarnessGoalResult,
    MoEFusionResult,
    MoERoutingWeights,
    ReferenceBlueprint,
)
from app.services.goal_harness import (
    all_goals_met,
    apply_rank_one_inline_fix,
    evaluate_edit_plan_goals,
    sync_edit_plan_motion_from_fusion,
)


def _base_blackboard() -> ProjectBlackboard:
    return ProjectBlackboard(
        project_id="proj_test",
        run_id="run_test",
        user_id="user_test",
        approved_candidates=[
            CandidateVideo(
                candidate_id="cand_1",
                project_id="proj_test",
                title="Test",
                source_type="sample_asset",
                concept="Test moment",
                topic_match_score=0.9,
                visual_quality_score=0.8,
                audio_quality_score=0.7,
                motion_energy_score=0.85,
                text_relevance_score=0.8,
                reference_style_fit_score=0.75,
                source_safety_score=1.0,
                overall_score=0.85,
                recommended_rank=1,
                reason="Strong test clip",
            )
        ],
    )


def _high_drama_blueprint() -> ReferenceBlueprint:
    return ReferenceBlueprint(
        blueprint_id="bp_1",
        project_id="proj_test",
        video_type="ranking_video",
        aspect_ratio="9:16",
        duration_sec=30.0,
        ranking_count=5,
        ranking_order="5_to_1",
        hook_duration_sec=2.0,
        average_item_duration_sec=4.0,
        outro_duration_sec=2.0,
        section_order=[],
        caption_style={"prominence": "high"},
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


def _fusion_without_rank_one_zoom() -> MoEFusionResult:
    return MoEFusionResult(
        fusion_id="fusion_1",
        round_id="round_1",
        hook_text="Top 5 picks",
        outro_text="Which wins?",
        motion_updates=[{"rank": 1, "zoom": False, "pan": False, "scale": 1.0}],
        routing_weights=MoERoutingWeights(round_id="round_1"),
    )


def test_evaluate_edit_plan_goals_flags_missing_rank_one_emphasis() -> None:
    blackboard = _base_blackboard()
    blackboard.reference_blueprint = _high_drama_blueprint()
    blackboard.moe_fusion = _fusion_without_rank_one_zoom()

    evaluations = evaluate_edit_plan_goals(blackboard)

    assert not all_goals_met(evaluations)
    rank_one_evaluation = next(
        evaluation for evaluation in evaluations if evaluation.goal_id == GOAL_RANK_ONE_EMPHASIS
    )
    assert rank_one_evaluation.met is False
    assert rank_one_evaluation.issue is not None


def test_apply_rank_one_inline_fix_updates_fusion_and_edit_plan() -> None:
    blackboard = _base_blackboard()
    blackboard.reference_blueprint = _high_drama_blueprint()
    blackboard.moe_fusion = _fusion_without_rank_one_zoom()
    blackboard.edit_plan = EditPlan(
        edit_plan_id="plan_1",
        project_id="proj_test",
        version=1,
        topic="test topic",
        output_aspect_ratio="9:16",
        output_duration_sec=20.0,
        hook_text="Hook",
        outro_text="Outro",
        sections=[],
        captions=[],
        audio_plan={},
        motion_plan=[{"rank": 1, "zoom": False, "pan": False, "scale": 1.0}],
        transition_plan=[],
        render_settings={},
        reference_blueprint_applied={},
        memory_influence={},
    )

    updated = apply_rank_one_inline_fix(blackboard)

    rank_one_motion = next(
        item for item in updated.moe_fusion.motion_updates if item.get("rank") == 1
    )
    assert rank_one_motion["zoom"] is True
    assert rank_one_motion["scale"] >= 1.15

    edit_plan_motion = next(
        item for item in updated.edit_plan.motion_plan if item.get("rank") == 1
    )
    assert edit_plan_motion["zoom"] is True


def test_sync_edit_plan_motion_from_fusion_only() -> None:
    blackboard = _base_blackboard()
    blackboard.moe_fusion = MoEFusionResult(
        fusion_id="fusion_2",
        round_id="round_2",
        hook_text="Hook",
        outro_text="Outro",
        motion_updates=[{"rank": 2, "zoom": True, "pan": True, "scale": 1.2}],
        routing_weights=MoERoutingWeights(round_id="round_2"),
    )
    blackboard.edit_plan = EditPlan(
        edit_plan_id="plan_2",
        project_id="proj_test",
        version=1,
        topic="topic",
        output_aspect_ratio="9:16",
        output_duration_sec=10.0,
        hook_text="Hook",
        outro_text="Outro",
        sections=[],
        captions=[],
        audio_plan={},
        motion_plan=[{"rank": 2, "zoom": False, "pan": False, "scale": 1.0}],
        transition_plan=[],
        render_settings={},
        reference_blueprint_applied={},
        memory_influence={},
    )

    updated = sync_edit_plan_motion_from_fusion(blackboard)
    motion_entry = updated.edit_plan.motion_plan[0]
    assert motion_entry["zoom"] is True
    assert motion_entry["pan"] is True
    assert motion_entry["scale"] == 1.2


def test_route_after_critic_retries_when_goals_unmet() -> None:
    blackboard = _base_blackboard()
    blackboard.harness_goals_met = False
    blackboard.harness_revision_count = 0

    route = route_after_critic({"blackboard": blackboard})

    assert route == HARNESS_ROUTE_RETRY


def test_route_after_critic_continues_when_goals_met() -> None:
    blackboard = _base_blackboard()
    blackboard.harness_goals_met = True

    route = route_after_critic({"blackboard": blackboard})

    assert route == HARNESS_ROUTE_CONTINUE


def test_route_after_critic_stops_retrying_at_max_revisions() -> None:
    blackboard = _base_blackboard()
    blackboard.harness_goals_met = False
    blackboard.harness_revision_count = MAX_HARNESS_REVISIONS

    route = route_after_critic({"blackboard": blackboard})

    assert route == HARNESS_ROUTE_CONTINUE


def test_route_after_critic_accepts_workflow_state() -> None:
    blackboard = _base_blackboard()
    blackboard.harness_goals_met = True
    blackboard.harness_goal_results = [
        HarnessGoalResult(goal_id=GOAL_RANK_ONE_EMPHASIS, met=True),
    ]
    state: WorkflowState = {"blackboard": blackboard}

    assert route_after_critic(state) == HARNESS_ROUTE_CONTINUE
