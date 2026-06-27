from dataclasses import dataclass, field
from typing import Any

from app.constants.video_constraints import (
    REJECTION_REASON_ASPECT_MISMATCH,
    REJECTION_REASON_DURATION_TOO_LONG,
    REJECTION_REASON_DURATION_TOO_SHORT,
    REJECTION_REASON_PROBE_FAILED,
    REJECTION_REASON_WRONG_ORIENTATION,
    REFERENCE_DURATION_TOLERANCE_RATIO,
    MIN_SOURCE_DURATION_SEC,
    SHORT_FORM_REFERENCE_MAX_SEC,
    SHORTS_SOURCE_ACCEPTANCE_MAX_SEC,
    YOUTUBE_SHORTS_MAX_DURATION_SEC,
)
from app.constants.video_sources import YOUTUBE_SEARCH_MODE_SHORTS
from app.constants.video_sources import (
    VIDEO_ORIENTATION_LANDSCAPE,
    VIDEO_ORIENTATION_MOBILE,
    VIDEO_ORIENTATION_UNKNOWN,
    detect_video_orientation_from_dimensions,
)
from app.schemas import ReferenceBlueprint


@dataclass
class ReferenceVideoConstraints:
    aspect_ratio: str
    target_orientation: str
    reference_duration_sec: float
    target_candidate_duration_sec: float
    rank_segment_duration_sec: float
    min_source_duration_sec: float
    max_source_duration_sec: float

    @classmethod
    def from_blueprint(cls, blueprint: ReferenceBlueprint) -> "ReferenceVideoConstraints":
        reference_duration = max(blueprint.duration_sec, MIN_SOURCE_DURATION_SEC)
        rank_segment = max(blueprint.average_item_duration_sec, MIN_SOURCE_DURATION_SEC)
        tolerance = max(reference_duration * REFERENCE_DURATION_TOLERANCE_RATIO, 2.0)
        max_duration = min(reference_duration + tolerance, SHORT_FORM_REFERENCE_MAX_SEC)
        min_duration = max(reference_duration - tolerance, MIN_SOURCE_DURATION_SEC)

        orientation = VIDEO_ORIENTATION_UNKNOWN
        if blueprint.aspect_ratio == "9:16":
            orientation = VIDEO_ORIENTATION_MOBILE
        elif blueprint.aspect_ratio in {"16:9", "4:3", "21:9"}:
            orientation = VIDEO_ORIENTATION_LANDSCAPE

        return cls(
            aspect_ratio=blueprint.aspect_ratio,
            target_orientation=orientation,
            reference_duration_sec=reference_duration,
            target_candidate_duration_sec=reference_duration,
            rank_segment_duration_sec=rank_segment,
            min_source_duration_sec=min_duration,
            max_source_duration_sec=max_duration,
        )

    def for_platform_search(self, youtube_search_mode: str | None) -> "ReferenceVideoConstraints":
        prefer_shorts = youtube_search_mode in {YOUTUBE_SEARCH_MODE_SHORTS, "shorts", None}
        if not prefer_shorts:
            return self
        return ReferenceVideoConstraints(
            aspect_ratio=self.aspect_ratio,
            target_orientation=self.target_orientation,
            reference_duration_sec=self.reference_duration_sec,
            target_candidate_duration_sec=self.target_candidate_duration_sec,
            rank_segment_duration_sec=self.rank_segment_duration_sec,
            min_source_duration_sec=MIN_SOURCE_DURATION_SEC,
            max_source_duration_sec=YOUTUBE_SHORTS_MAX_DURATION_SEC,
        )

    def for_source_acceptance(self, youtube_search_mode: str | None) -> "ReferenceVideoConstraints":
        prefer_shorts = youtube_search_mode in {YOUTUBE_SEARCH_MODE_SHORTS, "shorts", None}
        if not prefer_shorts:
            return self
        return ReferenceVideoConstraints(
            aspect_ratio=self.aspect_ratio,
            target_orientation=self.target_orientation,
            reference_duration_sec=self.reference_duration_sec,
            target_candidate_duration_sec=self.target_candidate_duration_sec,
            rank_segment_duration_sec=self.rank_segment_duration_sec,
            min_source_duration_sec=self.min_source_duration_sec,
            max_source_duration_sec=min(
                max(self.max_source_duration_sec, SHORTS_SOURCE_ACCEPTANCE_MAX_SEC),
                SHORT_FORM_REFERENCE_MAX_SEC,
            ),
        )


@dataclass
class VideoFitEvaluation:
    acceptable: bool
    fit_score: float
    rejection_reasons: list[str] = field(default_factory=list)
    duration_sec: float | None = None
    width: int | None = None
    height: int | None = None
    orientation: str = VIDEO_ORIENTATION_UNKNOWN
    aspect_ratio_hint: str = "unknown"

    def primary_rejection_reason(self) -> str | None:
        return self.rejection_reasons[0] if self.rejection_reasons else None


def evaluate_video_fit(
    *,
    duration_sec: float | None,
    width: int | None,
    height: int | None,
    orientation: str,
    aspect_ratio_hint: str,
    constraints: ReferenceVideoConstraints,
    preference_max_duration_sec: float | None = None,
    preference_min_duration_sec: float | None = None,
    blocked_orientations: set[str] | None = None,
) -> VideoFitEvaluation:
    rejection_reasons: list[str] = []
    fit_score = 1.0

    resolved_orientation = orientation
    if resolved_orientation == VIDEO_ORIENTATION_UNKNOWN:
        resolved_orientation = detect_video_orientation_from_dimensions(width, height)

    max_allowed = preference_max_duration_sec or constraints.max_source_duration_sec
    min_allowed = preference_min_duration_sec or constraints.min_source_duration_sec

    if duration_sec is not None:
        if duration_sec < min_allowed:
            rejection_reasons.append(REJECTION_REASON_DURATION_TOO_SHORT)
            fit_score -= 0.5
        elif duration_sec > max_allowed:
            rejection_reasons.append(REJECTION_REASON_DURATION_TOO_LONG)
            fit_score -= 0.7
        else:
            duration_delta = abs(duration_sec - constraints.target_candidate_duration_sec)
            tolerance = max(
                constraints.target_candidate_duration_sec * REFERENCE_DURATION_TOLERANCE_RATIO,
                2.0,
            )
            duration_penalty = min(duration_delta / tolerance, 1.0) * 0.25
            fit_score -= duration_penalty
    else:
        fit_score -= 0.15

    if constraints.target_orientation != VIDEO_ORIENTATION_UNKNOWN:
        if resolved_orientation == VIDEO_ORIENTATION_UNKNOWN:
            fit_score -= 0.1
        elif resolved_orientation != constraints.target_orientation:
            rejection_reasons.append(REJECTION_REASON_WRONG_ORIENTATION)
            fit_score -= 0.6
        elif blocked_orientations and resolved_orientation in blocked_orientations:
            rejection_reasons.append(REJECTION_REASON_WRONG_ORIENTATION)
            fit_score -= 0.8

    if (
        aspect_ratio_hint != "unknown"
        and constraints.aspect_ratio != "unknown"
        and aspect_ratio_hint != constraints.aspect_ratio
        and constraints.target_orientation != VIDEO_ORIENTATION_UNKNOWN
        and resolved_orientation == VIDEO_ORIENTATION_UNKNOWN
    ):
        rejection_reasons.append(REJECTION_REASON_ASPECT_MISMATCH)
        fit_score -= 0.4

    if duration_sec is None and width is None and height is None:
        if resolved_orientation == VIDEO_ORIENTATION_UNKNOWN:
            rejection_reasons.append(REJECTION_REASON_PROBE_FAILED)
            fit_score -= 0.2
        else:
            fit_score -= 0.1

    normalized_score = max(min(fit_score, 1.0), 0.0)
    acceptable = len(rejection_reasons) == 0

    return VideoFitEvaluation(
        acceptable=acceptable,
        fit_score=normalized_score,
        rejection_reasons=rejection_reasons,
        duration_sec=duration_sec,
        width=width,
        height=height,
        orientation=resolved_orientation,
        aspect_ratio_hint=aspect_ratio_hint,
    )


def build_rejection_message(evaluation: VideoFitEvaluation, constraints: ReferenceVideoConstraints) -> str:
    reason = evaluation.primary_rejection_reason()
    if reason == REJECTION_REASON_DURATION_TOO_LONG and evaluation.duration_sec is not None:
        minutes = evaluation.duration_sec / 60.0
        if minutes >= 1:
            return (
                f"Video is {minutes:.1f} min — too long for the {constraints.reference_duration_sec:.0f}s "
                f"reference (accepted range {constraints.min_source_duration_sec:.0f}–"
                f"{constraints.max_source_duration_sec:.0f}s)"
            )
        return (
            f"Video is {evaluation.duration_sec:.0f}s — outside reference range "
            f"{constraints.min_source_duration_sec:.0f}–{constraints.max_source_duration_sec:.0f}s"
        )
    if reason == REJECTION_REASON_DURATION_TOO_SHORT:
        return (
            f"Video is too short — need ~{constraints.target_candidate_duration_sec:.0f}s "
            f"(min {constraints.min_source_duration_sec:.0f}s)"
        )
    if reason == REJECTION_REASON_WRONG_ORIENTATION:
        return f"Wrong orientation — need {constraints.aspect_ratio}, got {evaluation.aspect_ratio_hint}"
    if reason == REJECTION_REASON_ASPECT_MISMATCH:
        return f"Aspect ratio mismatch — need {constraints.aspect_ratio}"
    if reason == REJECTION_REASON_PROBE_FAILED:
        return "Could not verify video duration or aspect ratio"
    return "Video does not match reference constraints"


def constraints_summary(constraints: ReferenceVideoConstraints) -> dict[str, Any]:
    return {
        "aspect_ratio": constraints.aspect_ratio,
        "target_orientation": constraints.target_orientation,
        "reference_duration_sec": constraints.reference_duration_sec,
        "target_candidate_duration_sec": constraints.target_candidate_duration_sec,
        "rank_segment_duration_sec": constraints.rank_segment_duration_sec,
        "min_source_duration_sec": constraints.min_source_duration_sec,
        "max_source_duration_sec": constraints.max_source_duration_sec,
    }
