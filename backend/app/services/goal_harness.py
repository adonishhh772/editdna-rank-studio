from dataclasses import dataclass

from app.blackboard import ProjectBlackboard
from app.constants.harness import (
    EDIT_PLAN_GOALS,
    GOAL_CANDIDATES_SELECTED,
    GOAL_MOE_COMPLETE,
    GOAL_NO_CONFLICTS,
    GOAL_RANK_ONE_EMPHASIS,
)
from app.constants.moe import EXPERT_DOMAIN_MOTION, MESSAGE_TYPE_CONFLICT, MESSAGE_TYPE_FEEDBACK
from app.db import new_id, utc_now
from app.schemas import AgentMessage, HarnessGoalResult


@dataclass(frozen=True)
class GoalEvaluation:
    goal_id: str
    met: bool
    issue: str | None = None


def evaluate_edit_plan_goals(blackboard: ProjectBlackboard) -> list[GoalEvaluation]:
    evaluations: list[GoalEvaluation] = []

    candidates = blackboard.approved_candidates or blackboard.selected_candidates
    evaluations.append(
        GoalEvaluation(
            goal_id=GOAL_CANDIDATES_SELECTED,
            met=bool(candidates),
            issue=None if candidates else "No approved candidates selected",
        )
    )

    if blackboard.moe_fusion and len(blackboard.expert_proposals) < 4:
        evaluations.append(
            GoalEvaluation(
                goal_id=GOAL_MOE_COMPLETE,
                met=False,
                issue="Incomplete MoE expert participation",
            )
        )
    else:
        evaluations.append(GoalEvaluation(goal_id=GOAL_MOE_COMPLETE, met=True))

    moe_conflicts = [
        message
        for message in blackboard.agent_messages
        if message.message_type == MESSAGE_TYPE_CONFLICT
    ]
    if moe_conflicts:
        conflict_issues = [
            f"MoE conflict ({conflict.from_agent_name}): {conflict.payload.get('issue', 'unresolved')}"
            for conflict in moe_conflicts
        ]
        evaluations.append(
            GoalEvaluation(
                goal_id=GOAL_NO_CONFLICTS,
                met=False,
                issue="; ".join(conflict_issues),
            )
        )
    else:
        evaluations.append(GoalEvaluation(goal_id=GOAL_NO_CONFLICTS, met=True))

    rank_one_met = True
    rank_one_issue: str | None = None
    if (
        blackboard.reference_blueprint
        and blackboard.reference_blueprint.final_rank_drama_level == "high"
    ):
        fusion = blackboard.moe_fusion
        if fusion:
            rank_one_motion = next(
                (item for item in fusion.motion_updates if item.get("rank") == 1),
                None,
            )
            if not rank_one_motion or not rank_one_motion.get("zoom"):
                rank_one_met = False
                rank_one_issue = "Ensure rank #1 has stronger visual emphasis"
        else:
            rank_one_met = False
            rank_one_issue = "Ensure rank #1 has stronger visual emphasis"

    evaluations.append(
        GoalEvaluation(
            goal_id=GOAL_RANK_ONE_EMPHASIS,
            met=rank_one_met,
            issue=rank_one_issue,
        )
    )

    return evaluations


def build_harness_goal_results(evaluations: list[GoalEvaluation]) -> list[HarnessGoalResult]:
    return [
        HarnessGoalResult(
            goal_id=evaluation.goal_id,
            met=evaluation.met,
            issue=evaluation.issue,
        )
        for evaluation in evaluations
    ]


def all_goals_met(evaluations: list[GoalEvaluation]) -> bool:
    return all(evaluation.met for evaluation in evaluations)


def unmet_goal_issues(evaluations: list[GoalEvaluation]) -> list[str]:
    return [evaluation.issue for evaluation in evaluations if not evaluation.met and evaluation.issue]


def apply_rank_one_inline_fix(blackboard: ProjectBlackboard) -> ProjectBlackboard:
    if not blackboard.moe_fusion:
        return blackboard

    motion_updates = list(blackboard.moe_fusion.motion_updates)
    rank_one_index = next(
        (index for index, item in enumerate(motion_updates) if item.get("rank") == 1),
        None,
    )
    if rank_one_index is not None:
        motion_updates[rank_one_index] = {
            **motion_updates[rank_one_index],
            "zoom": True,
            "scale": max(float(motion_updates[rank_one_index].get("scale", 1.0)), 1.15),
        }
    else:
        motion_updates.append({"rank": 1, "zoom": True, "pan": False, "scale": 1.15})
    blackboard.moe_fusion.motion_updates = motion_updates
    return sync_edit_plan_motion_from_fusion(blackboard)


def sync_edit_plan_motion_from_fusion(blackboard: ProjectBlackboard) -> ProjectBlackboard:
    if not blackboard.edit_plan or not blackboard.moe_fusion:
        return blackboard

    motion_by_rank = {
        int(item["rank"]): item
        for item in blackboard.moe_fusion.motion_updates
        if item.get("rank") is not None
    }
    updated_motion_plan: list[dict] = []
    for entry in blackboard.edit_plan.motion_plan:
        rank = int(entry.get("rank", 0))
        fusion_motion = motion_by_rank.get(rank)
        if fusion_motion is None:
            updated_motion_plan.append(entry)
            continue
        updated_motion_plan.append(
            {
                **entry,
                "zoom": bool(fusion_motion.get("zoom", entry.get("zoom"))),
                "pan": bool(fusion_motion.get("pan", entry.get("pan"))),
                "scale": float(fusion_motion.get("scale", entry.get("scale", 1.0))),
            }
        )
    blackboard.edit_plan.motion_plan = updated_motion_plan
    return blackboard


def inject_harness_feedback(
    blackboard: ProjectBlackboard,
    evaluations: list[GoalEvaluation],
) -> ProjectBlackboard:
    for evaluation in evaluations:
        if evaluation.met or not evaluation.issue:
            continue
        blackboard.agent_messages.append(
            AgentMessage(
                message_id=new_id("msg"),
                project_id=blackboard.project_id,
                run_id=blackboard.run_id,
                round_id="harness_retry",
                from_agent_id="critic_agent",
                from_agent_name="Critic Agent",
                to_agent_id=None,
                message_type=MESSAGE_TYPE_FEEDBACK,
                domain=EXPERT_DOMAIN_MOTION
                if evaluation.goal_id == GOAL_RANK_ONE_EMPHASIS
                else "harness",
                payload={"issue": evaluation.issue, "goal_id": evaluation.goal_id},
                created_at=utc_now(),
            )
        )
    return blackboard


def apply_harness_remediation(
    blackboard: ProjectBlackboard,
    evaluations: list[GoalEvaluation],
) -> ProjectBlackboard:
    unmet = [evaluation for evaluation in evaluations if not evaluation.met]
    needs_rank_one_fix = any(
        evaluation.goal_id == GOAL_RANK_ONE_EMPHASIS for evaluation in unmet
    )
    if needs_rank_one_fix:
        blackboard = apply_rank_one_inline_fix(blackboard)
    return inject_harness_feedback(blackboard, unmet)


def reset_moe_state_for_retry(blackboard: ProjectBlackboard) -> ProjectBlackboard:
    blackboard.expert_proposals = []
    blackboard.moe_routing = None
    blackboard.moe_fusion = None
    blackboard.edit_plan = None
    return blackboard


def expected_goal_ids() -> tuple[str, ...]:
    return EDIT_PLAN_GOALS
