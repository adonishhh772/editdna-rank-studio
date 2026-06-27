from typing import Any

from app.constants.video_constraints import VIDEO_PREFERENCES_MEMORY_KEY
from app.services.candidate_preference_service import get_video_preferences

APPROVED_DURATION_MATCH_BOOST = 0.12
APPROVED_ORIENTATION_MATCH_BOOST = 0.08
APPROVED_ASPECT_MATCH_BOOST = 0.05
REJECTED_SIMILARITY_PENALTY = 0.18
MAX_PREFERENCE_SCORE_DELTA = 0.35
DURATION_SIMILARITY_TOLERANCE_SEC = 4.0
LIGHTWEIGHT_SELECTION_MIN_APPROVED = 2
LIGHTWEIGHT_SELECTION_MIN_DELTA = 0.12


def compute_preference_learning_adjustment(
    *,
    duration_sec: float | None,
    orientation: str | None,
    aspect_ratio_hint: str | None,
    memory_context: dict[str, Any],
    target_duration_sec: float | None = None,
) -> tuple[float, list[str]]:
    preferences = get_video_preferences(memory_context)
    adjustment = 0.0
    reasons: list[str] = []

    preferred_duration = preferences.get("preferred_duration_sec")
    if isinstance(preferred_duration, (int, float)):
        target = float(preferred_duration)
    elif target_duration_sec is not None:
        target = target_duration_sec
    else:
        target = None

    for example in preferences.get("approved_examples", []):
        example_duration = example.get("duration_sec")
        if _duration_matches(duration_sec, example_duration, target):
            adjustment += APPROVED_DURATION_MATCH_BOOST
            reasons.append("Matches approved duration profile")
        if orientation and example.get("orientation") == orientation:
            adjustment += APPROVED_ORIENTATION_MATCH_BOOST
            if "Matches approved orientation" not in reasons:
                reasons.append("Matches approved orientation")
        if aspect_ratio_hint and example.get("aspect_ratio_hint") == aspect_ratio_hint:
            adjustment += APPROVED_ASPECT_MATCH_BOOST

    for example in preferences.get("rejected_examples", []):
        if _is_similar_to_example(duration_sec, orientation, aspect_ratio_hint, example):
            adjustment -= REJECTED_SIMILARITY_PENALTY
            concept = example.get("concept") or "prior clip"
            reasons.append(f"Similar to rejected '{concept}'")

    capped = max(min(adjustment, MAX_PREFERENCE_SCORE_DELTA), -MAX_PREFERENCE_SCORE_DELTA)
    return capped, reasons[:4]


def format_video_preferences_for_analysis(memory_context: dict[str, Any]) -> str:
    preferences = get_video_preferences(memory_context)
    approved = preferences.get("approved_examples", [])
    rejected = preferences.get("rejected_examples", [])
    notes = preferences.get("notes", [])
    blocked = preferences.get("blocked_orientations", [])
    max_duration = preferences.get("max_duration_sec")
    preferred_duration = preferences.get("preferred_duration_sec")

    if not approved and not rejected and not notes:
        return "No prior approve/reject learning yet for this project."

    lines = [
        "Use these learned preferences from human approve/reject decisions:",
    ]

    if preferred_duration:
        lines.append(f"- Preferred full-source duration: ~{float(preferred_duration):.0f}s")
    if max_duration:
        lines.append(f"- Avoid sources longer than ~{float(max_duration):.0f}s")
    if blocked:
        lines.append(f"- Blocked orientations: {', '.join(str(item) for item in blocked)}")

    for note in notes[-6:]:
        lines.append(f"- {note}")

    if approved:
        lines.append("- Approved examples (prefer similar duration/orientation):")
        for example in approved[-4:]:
            lines.append(_format_example_line(example, positive=True))

    if rejected:
        lines.append("- Rejected examples (avoid similar style):")
        for example in rejected[-4:]:
            lines.append(_format_example_line(example, positive=False))

    lines.append(
        "Score reference_style_fit_score higher when the candidate resembles approved examples "
        "and lower when it resembles rejected examples."
    )
    return "\n".join(lines)


def should_use_lightweight_selection(
    memory_context: dict[str, Any],
    *,
    duration_sec: float | None,
    orientation: str | None,
    aspect_ratio_hint: str | None,
    target_duration_sec: float | None = None,
) -> tuple[bool, list[str]]:
    preferences = get_video_preferences(memory_context)
    approved_count = len(preferences.get("approved_examples", []))
    if approved_count < LIGHTWEIGHT_SELECTION_MIN_APPROVED:
        return False, []

    delta, reasons = compute_preference_learning_adjustment(
        duration_sec=duration_sec,
        orientation=orientation,
        aspect_ratio_hint=aspect_ratio_hint,
        memory_context=memory_context,
        target_duration_sec=target_duration_sec,
    )
    if delta >= LIGHTWEIGHT_SELECTION_MIN_DELTA and reasons:
        return True, reasons
    return False, []


def summarize_preferences_for_ui(memory_context: dict[str, Any]) -> dict[str, Any]:
    preferences = get_video_preferences(memory_context)
    return {
        "notes": list(preferences.get("notes", []))[-10:],
        "approved_examples": list(preferences.get("approved_examples", []))[-8:],
        "rejected_examples": list(preferences.get("rejected_examples", []))[-8:],
        "blocked_orientations": list(preferences.get("blocked_orientations", [])),
        "max_duration_sec": preferences.get("max_duration_sec"),
        "preferred_duration_sec": preferences.get("preferred_duration_sec"),
        "has_learning": bool(
            preferences.get("notes")
            or preferences.get("approved_examples")
            or preferences.get("rejected_examples")
        ),
    }


def _format_example_line(example: dict[str, Any], positive: bool) -> str:
    concept = example.get("concept") or "clip"
    duration = example.get("duration_sec")
    orientation = example.get("orientation") or "unknown"
    prefix = "  + " if positive else "  - "
    if isinstance(duration, (int, float)):
        return f"{prefix}{concept}: {float(duration):.0f}s {orientation}"
    return f"{prefix}{concept}: {orientation}"


def _duration_matches(
    probe_duration: float | None,
    example_duration: Any,
    target_duration: float | None,
) -> bool:
    if probe_duration is None:
        return False
    if isinstance(example_duration, (int, float)):
        if abs(probe_duration - float(example_duration)) <= DURATION_SIMILARITY_TOLERANCE_SEC:
            return True
    if target_duration is not None:
        return abs(probe_duration - target_duration) <= DURATION_SIMILARITY_TOLERANCE_SEC
    return False


def _is_similar_to_example(
    duration_sec: float | None,
    orientation: str | None,
    aspect_ratio_hint: str | None,
    example: dict[str, Any],
) -> bool:
    matches = 0
    if duration_sec is not None and isinstance(example.get("duration_sec"), (int, float)):
        if abs(duration_sec - float(example["duration_sec"])) <= DURATION_SIMILARITY_TOLERANCE_SEC:
            matches += 1
    if orientation and example.get("orientation") == orientation:
        matches += 1
    if aspect_ratio_hint and example.get("aspect_ratio_hint") == aspect_ratio_hint:
        matches += 1
    return matches >= 2 or (matches == 1 and duration_sec is not None)
