from typing import Any

from app.constants.video_constraints import (
    FEEDBACK_TYPE_APPROVE,
    FEEDBACK_TYPE_REJECT,
    PREFERENCE_DECISION_APPROVE,
    PREFERENCE_DECISION_REJECT,
    REJECTION_REASON_DURATION_TOO_LONG,
    REJECTION_REASON_WRONG_ORIENTATION,
    VIDEO_PREFERENCES_MEMORY_KEY,
)
from app.db import new_id, utc_now
from app.schemas import CandidateVideo, FeedbackEvent, ReferenceBlueprint
from app.services.video_constraint_service import ReferenceVideoConstraints, VideoFitEvaluation


def get_video_preferences(memory_context: dict[str, Any]) -> dict[str, Any]:
    preferences = memory_context.get(VIDEO_PREFERENCES_MEMORY_KEY)
    if isinstance(preferences, dict):
        return preferences
    return {
        "rejected_examples": [],
        "approved_examples": [],
        "blocked_orientations": [],
        "max_duration_sec": None,
        "notes": [],
    }


def preference_max_duration_sec(memory_context: dict[str, Any]) -> float | None:
    preferences = get_video_preferences(memory_context)
    value = preferences.get("max_duration_sec")
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return None


def preference_blocked_orientations(memory_context: dict[str, Any]) -> set[str]:
    preferences = get_video_preferences(memory_context)
    blocked = preferences.get("blocked_orientations")
    if isinstance(blocked, list):
        return {str(item) for item in blocked if item}
    return set()


def build_candidate_feedback_event(
    *,
    blackboard_user_id: str,
    project_id: str,
    run_id: str,
    candidate: CandidateVideo,
    decision: str,
    evaluation: VideoFitEvaluation | None,
    constraints: ReferenceVideoConstraints | None,
    feedback_text: str | None = None,
) -> FeedbackEvent:
    metadata = {
        "duration_sec": candidate.duration_sec or evaluation.duration_sec if evaluation else None,
        "orientation": evaluation.orientation if evaluation else None,
        "aspect_ratio_hint": evaluation.aspect_ratio_hint if evaluation else None,
        "source_url": candidate.source_url,
        "concept": candidate.concept,
        "rejection_reasons": evaluation.rejection_reasons if evaluation else [],
    }
    if constraints:
        metadata["constraints"] = {
            "aspect_ratio": constraints.aspect_ratio,
            "target_candidate_duration_sec": constraints.target_candidate_duration_sec,
            "rank_segment_duration_sec": constraints.rank_segment_duration_sec,
            "min_source_duration_sec": constraints.min_source_duration_sec,
            "max_source_duration_sec": constraints.max_source_duration_sec,
        }

    auto_text = _build_auto_feedback_text(decision, candidate, evaluation, constraints)
    resolved_text = feedback_text.strip() if feedback_text and feedback_text.strip() else auto_text

    return FeedbackEvent(
        feedback_id=new_id("fb"),
        project_id=project_id,
        run_id=run_id,
        user_id=blackboard_user_id,
        feedback_type=FEEDBACK_TYPE_APPROVE if decision == PREFERENCE_DECISION_APPROVE else FEEDBACK_TYPE_REJECT,
        target_type="candidate",
        target_id=candidate.candidate_id,
        feedback_text=resolved_text,
        before_state={"candidate": candidate.model_dump(), "metadata": metadata},
        after_state={"decision": decision},
        created_at=utc_now(),
    )


def apply_candidate_decision_to_preferences(
    memory_context: dict[str, Any],
    *,
    candidate: CandidateVideo,
    decision: str,
    evaluation: VideoFitEvaluation | None,
    constraints: ReferenceVideoConstraints | None,
) -> dict[str, Any]:
    preferences = get_video_preferences(memory_context)
    example = _build_preference_example(candidate, evaluation, constraints)

    if decision == PREFERENCE_DECISION_REJECT:
        rejected_examples = list(preferences.get("rejected_examples", []))
        rejected_examples.append(example)
        preferences["rejected_examples"] = rejected_examples[-20:]

        if evaluation and REJECTION_REASON_DURATION_TOO_LONG in evaluation.rejection_reasons:
            current_max = preferences.get("max_duration_sec")
            duration = evaluation.duration_sec or candidate.duration_sec
            if duration and constraints:
                tightened = min(constraints.max_source_duration_sec, duration * 0.75)
                if current_max is None or tightened < float(current_max):
                    preferences["max_duration_sec"] = round(tightened, 1)

        if evaluation and REJECTION_REASON_WRONG_ORIENTATION in evaluation.rejection_reasons:
            blocked = set(preferences.get("blocked_orientations", []))
            if evaluation.orientation:
                blocked.add(evaluation.orientation)
            preferences["blocked_orientations"] = sorted(blocked)

        note = _build_preference_note(PREFERENCE_DECISION_REJECT, example)
        notes = list(preferences.get("notes", []))
        notes.append(note)
        preferences["notes"] = notes[-30:]

    if decision == PREFERENCE_DECISION_APPROVE:
        approved_examples = list(preferences.get("approved_examples", []))
        approved_examples.append(example)
        preferences["approved_examples"] = approved_examples[-20:]
        approved_durations = [
            float(item["duration_sec"])
            for item in approved_examples
            if isinstance(item.get("duration_sec"), (int, float))
        ]
        if approved_durations:
            preferences["preferred_duration_sec"] = round(
                sum(approved_durations) / len(approved_durations),
                1,
            )
        note = _build_preference_note(PREFERENCE_DECISION_APPROVE, example)
        notes = list(preferences.get("notes", []))
        notes.append(note)
        preferences["notes"] = notes[-30:]

    memory_context[VIDEO_PREFERENCES_MEMORY_KEY] = preferences
    return memory_context


async def persist_candidate_preference_memory(
    *,
    user_id: str,
    project_id: str,
    run_id: str,
    agent_id: str,
    feedback: FeedbackEvent,
) -> None:
    try:
        from app.integrations.mubit_client import MubitMemoryClient

        client = MubitMemoryClient(run_id=run_id)
        content = feedback.feedback_text or feedback.feedback_type
        metadata = {
            "memory_scope": "episodic",
            "feedback_type": feedback.feedback_type,
            "target_type": feedback.target_type,
            "target_id": feedback.target_id,
        }
        await client.remember_episodic(
            user_id=user_id,
            project_id=project_id,
            run_id=run_id,
            agent_id=agent_id,
            content=content,
            metadata=metadata,
        )

        if feedback.feedback_type in {FEEDBACK_TYPE_REJECT, FEEDBACK_TYPE_APPROVE}:
            await client.remember_long_term(
                user_id=user_id,
                project_id=project_id,
                run_id=run_id,
                agent_id=agent_id,
                content=content,
                metadata={
                    **metadata,
                    "memory_scope": "long_term",
                    "learning_type": "video_preference",
                },
            )
    except Exception:
        return


def _build_preference_example(
    candidate: CandidateVideo,
    evaluation: VideoFitEvaluation | None,
    constraints: ReferenceVideoConstraints | None,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "concept": candidate.concept,
        "source_url": candidate.source_url,
        "duration_sec": candidate.duration_sec or (evaluation.duration_sec if evaluation else None),
        "orientation": evaluation.orientation if evaluation else None,
        "aspect_ratio_hint": evaluation.aspect_ratio_hint if evaluation else None,
        "rejection_reasons": evaluation.rejection_reasons if evaluation else [],
        "max_allowed_sec": constraints.max_source_duration_sec if constraints else None,
    }


def _build_preference_note(decision: str, example: dict[str, Any]) -> str:
    duration = example.get("duration_sec")
    orientation = example.get("orientation") or "unknown"
    concept = example.get("concept") or "clip"
    if decision == PREFERENCE_DECISION_REJECT:
        if duration:
            return f"Rejected {concept}: {duration:.0f}s {orientation} clip not preferred"
        return f"Rejected {concept}: {orientation} clip not preferred"
    if duration:
        return f"Approved {concept}: {duration:.0f}s {orientation} clip preferred"
    return f"Approved {concept}: {orientation} clip preferred"


def _build_auto_feedback_text(
    decision: str,
    candidate: CandidateVideo,
    evaluation: VideoFitEvaluation | None,
    constraints: ReferenceVideoConstraints | None,
) -> str:
    if decision == PREFERENCE_DECISION_APPROVE:
        duration = candidate.duration_sec or (evaluation.duration_sec if evaluation else None)
        orientation = evaluation.orientation if evaluation else "unknown"
        if duration and constraints:
            return (
                f"Approved {candidate.concept}: {duration:.0f}s {orientation} clip "
                f"fits ~{constraints.target_candidate_duration_sec:.0f}s reference"
            )
        return f"Approved {candidate.concept}"

    if evaluation and evaluation.rejection_reasons:
        reasons = ", ".join(evaluation.rejection_reasons)
        return f"Rejected {candidate.concept}: {reasons} — this style is not preferred"

    duration = candidate.duration_sec
    if duration and constraints and duration > constraints.max_source_duration_sec:
        return (
            f"Rejected {candidate.concept}: {duration / 60:.1f} min clip too long "
            f"for {constraints.reference_duration_sec:.0f}s reference — not preferred"
        )
    return f"Rejected {candidate.concept} — not preferred for this reference style"
