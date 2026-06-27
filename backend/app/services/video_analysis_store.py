from typing import Any

from app.blackboard import ProjectBlackboard
from app.constants.video_analysis import (
    ANALYSIS_SOURCE_GEMINI,
    ANALYSIS_SOURCE_LIGHTWEIGHT,
    CANDIDATE_ANALYSIS_TYPE,
    REFERENCE_ANALYSIS_TYPE,
    VIDEO_ANALYSES_MEMORY_KEY,
)
from app.schemas import CandidateVideo, ReferenceBlueprint


def _empty_video_analyses() -> dict[str, Any]:
    return {
        "reference": None,
        "candidates": {},
    }


def get_video_analyses(memory_context: dict[str, Any]) -> dict[str, Any]:
    stored = memory_context.get(VIDEO_ANALYSES_MEMORY_KEY)
    if not isinstance(stored, dict):
        return _empty_video_analyses()
    return {
        "reference": stored.get("reference"),
        "candidates": dict(stored.get("candidates") or {}),
    }


def _build_reference_analysis_entry(blueprint: ReferenceBlueprint) -> dict[str, Any]:
    return {
        "analysis_type": REFERENCE_ANALYSIS_TYPE,
        "blueprint_id": blueprint.blueprint_id,
        "ranking_count": blueprint.ranking_count,
        "ranking_order": blueprint.ranking_order,
        "duration_sec": blueprint.duration_sec,
        "aspect_ratio": blueprint.aspect_ratio,
        "hook_style": blueprint.hook_style,
        "hook_duration_sec": blueprint.hook_duration_sec,
        "average_item_duration_sec": blueprint.average_item_duration_sec,
        "outro_duration_sec": blueprint.outro_duration_sec,
        "rank_reveal_style": blueprint.rank_reveal_style,
        "final_rank_drama_level": blueprint.final_rank_drama_level,
        "caption_style": blueprint.caption_style,
        "motion_style": blueprint.motion_style,
        "pacing_style": blueprint.pacing_style,
        "audio_style": blueprint.audio_style,
        "section_order": [section.model_dump() for section in blueprint.section_order],
        "confidence": blueprint.confidence,
    }


def _build_candidate_analysis_entry(
    candidate: CandidateVideo,
    *,
    analysis_source: str,
) -> dict[str, Any]:
    return {
        "analysis_type": CANDIDATE_ANALYSIS_TYPE,
        "candidate_id": candidate.candidate_id,
        "rank": candidate.recommended_rank,
        "title": candidate.title,
        "concept": candidate.concept,
        "reason": candidate.reason,
        "highlight_reason": candidate.highlight_reason,
        "video_moment_title": candidate.video_moment_title,
        "clip_start_sec": candidate.clip_start_sec,
        "clip_end_sec": candidate.clip_end_sec,
        "duration_sec": candidate.duration_sec,
        "analysis_source": analysis_source,
        "scores": {
            "topic_match": candidate.topic_match_score,
            "visual_quality": candidate.visual_quality_score,
            "audio_quality": candidate.audio_quality_score,
            "motion_energy": candidate.motion_energy_score,
            "text_relevance": candidate.text_relevance_score,
            "reference_style_fit": candidate.reference_style_fit_score,
            "source_safety": candidate.source_safety_score,
            "story_coherence": candidate.story_coherence_score,
            "overall": candidate.overall_score,
        },
    }


def save_reference_video_analysis(blackboard: ProjectBlackboard) -> None:
    if not blackboard.reference_blueprint:
        return

    analyses = get_video_analyses(blackboard.memory_context)
    analyses["reference"] = _build_reference_analysis_entry(blackboard.reference_blueprint)
    blackboard.memory_context[VIDEO_ANALYSES_MEMORY_KEY] = analyses


def save_candidate_video_analysis(
    blackboard: ProjectBlackboard,
    candidate: CandidateVideo,
    *,
    analysis_source: str = ANALYSIS_SOURCE_GEMINI,
) -> None:
    analyses = get_video_analyses(blackboard.memory_context)
    analyses["candidates"][candidate.candidate_id] = _build_candidate_analysis_entry(
        candidate,
        analysis_source=analysis_source,
    )
    blackboard.memory_context[VIDEO_ANALYSES_MEMORY_KEY] = analyses


def sync_candidate_analyses_from_approved(blackboard: ProjectBlackboard) -> None:
    candidates = blackboard.approved_candidates or blackboard.selected_candidates
    if not candidates:
        return

    analyses = get_video_analyses(blackboard.memory_context)
    for candidate in candidates:
        if candidate.candidate_id in analyses["candidates"]:
            continue
        source = (
            ANALYSIS_SOURCE_LIGHTWEIGHT
            if "learned preferences" in candidate.reason.lower()
            else ANALYSIS_SOURCE_GEMINI
        )
        analyses["candidates"][candidate.candidate_id] = _build_candidate_analysis_entry(
            candidate,
            analysis_source=source,
        )
    blackboard.memory_context[VIDEO_ANALYSES_MEMORY_KEY] = analyses


def build_edit_video_insights(blackboard: ProjectBlackboard) -> dict[str, Any]:
    sync_candidate_analyses_from_approved(blackboard)
    analyses = get_video_analyses(blackboard.memory_context)
    candidates = blackboard.approved_candidates or blackboard.selected_candidates
    ordered_candidates: list[dict[str, Any]] = []

    for candidate in sorted(candidates, key=lambda item: item.recommended_rank or 99):
        stored = analyses["candidates"].get(candidate.candidate_id)
        if stored:
            ordered_candidates.append(stored)
        else:
            ordered_candidates.append(
                _build_candidate_analysis_entry(candidate, analysis_source=ANALYSIS_SOURCE_GEMINI)
            )

    return {
        "reference": analyses["reference"],
        "candidates": ordered_candidates,
    }


def get_candidate_analysis_by_rank(
    blackboard: ProjectBlackboard,
    rank: int,
) -> dict[str, Any] | None:
    insights = build_edit_video_insights(blackboard)
    for entry in insights["candidates"]:
        if entry.get("rank") == rank:
            return entry
    return None
