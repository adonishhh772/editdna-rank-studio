import pytest

from app.schemas import CandidateVideo, RankedClip
from app.services.story_coherence_service import (
    compute_weighted_overall_score,
    derive_video_moment_title,
    enrich_candidate_story_fields,
    enrich_ranked_clip_story_fields,
    evaluate_edit_plan_story_coherence,
    is_generic_analysis_reason,
)


def _candidate(**overrides) -> CandidateVideo:
    base = {
        "candidate_id": "cand-1",
        "project_id": "proj-1",
        "title": "Top 5 Most Embarrassing Video Moments - TikTok",
        "source_type": "public_url_reference",
        "concept": "Harry Styles pants rip",
        "topic_match_score": 0.95,
        "visual_quality_score": 0.7,
        "audio_quality_score": 0.65,
        "motion_energy_score": 0.75,
        "text_relevance_score": 0.95,
        "reference_style_fit_score": 0.85,
        "source_safety_score": 1.0,
        "overall_score": 1.0,
        "recommended_rank": 3,
        "reason": "Generic",
        "highlight_reason": (
            "Harry Styles ripping his pants on stage with on-screen text about the wardrobe malfunction"
        ),
    }
    base.update(overrides)
    return CandidateVideo(**base)


def test_is_generic_analysis_reason_detects_reference_aligned_text() -> None:
    assert is_generic_analysis_reason("Reference-aligned highlight for rank 4 (5.0s window)")
    assert not is_generic_analysis_reason("Harry Styles ripping his pants on stage")


def test_derive_video_moment_title_prefers_highlight_over_source_title() -> None:
    candidate = _candidate()
    assert derive_video_moment_title(candidate).startswith("Harry Styles ripping his pants")


def test_weighted_overall_score_is_not_inflated_by_style_fit_only() -> None:
    candidate = _candidate(
        reference_style_fit_score=1.0,
        audio_quality_score=0.0,
        motion_energy_score=0.0,
        highlight_reason="Reference-aligned highlight for rank 4 (5.0s window)",
    )
    enriched = enrich_candidate_story_fields(candidate)
    assert enriched.overall_score < 0.85


def test_enrich_ranked_clip_uses_video_moment_title_and_rank_label() -> None:
    candidate = _candidate()
    section = RankedClip(
        rank=3,
        candidate_id="cand-1",
        title=candidate.title,
        source_file_path="/tmp/clip.mp4",
        clip_start_sec=4.5,
        clip_end_sec=8.2,
        label_text="Old label",
        reason=candidate.highlight_reason or "",
        highlight_reason=candidate.highlight_reason,
    )
    enriched = enrich_ranked_clip_story_fields(section, candidate)
    assert enriched.title.startswith("Harry Styles")
    assert enriched.source_video_title == candidate.title
    assert enriched.label_text.startswith("#3 ")
    assert enriched.voiceover_text.startswith("Number 3:")
    assert enriched.story_coherence_score > 0.5


def test_evaluate_edit_plan_story_coherence_flags_generic_reasons() -> None:
    candidate = _candidate(
        highlight_reason="Reference-aligned highlight for rank 4 (5.0s window)",
        reason="Reference-aligned highlight for rank 4 (5.0s window)",
    )
    section = RankedClip(
        rank=4,
        candidate_id="cand-4",
        title=candidate.title,
        source_file_path="/tmp/clip.mp4",
        clip_start_sec=9.0,
        clip_end_sec=14.0,
        label_text="#4 clip",
        reason=candidate.reason,
        highlight_reason=candidate.highlight_reason,
    )
    section = enrich_ranked_clip_story_fields(section, candidate)
    story_ready, issues = evaluate_edit_plan_story_coherence([section])
    assert story_ready is False
    assert any("generic" in issue.lower() for issue in issues)
