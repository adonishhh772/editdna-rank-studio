from app.blackboard import ProjectBlackboard
from app.constants.video_analysis import (
    ANALYSIS_SOURCE_GEMINI,
    ANALYSIS_SOURCE_LIGHTWEIGHT,
    VIDEO_ANALYSES_MEMORY_KEY,
)
from app.db import new_id
from app.schemas import CandidateVideo, ReferenceBlueprint, ReferenceSection
from app.services.video_analysis_store import (
    build_edit_video_insights,
    get_video_analyses,
    save_candidate_video_analysis,
    save_reference_video_analysis,
    sync_candidate_analyses_from_approved,
)


def _sample_blueprint(project_id: str) -> ReferenceBlueprint:
    return ReferenceBlueprint(
        blueprint_id=new_id("bp"),
        project_id=project_id,
        video_type="ranking_video",
        ranking_count=3,
        ranking_order="5_to_1",
        hook_duration_sec=3.0,
        average_item_duration_sec=4.0,
        outro_duration_sec=2.0,
        duration_sec=20.0,
        aspect_ratio="9:16",
        hook_style="question",
        rank_reveal_style="countdown",
        final_rank_drama_level="high",
        caption_style={"prominence": "high", "case": "upper"},
        text_overlay_style={},
        transition_style={},
        audio_style={"mood": "energetic"},
        motion_style={"energy": "high"},
        pacing_style={"tempo": "fast"},
        section_order=[
            ReferenceSection(
                name="Hook",
                start_sec=0.0,
                end_sec=3.0,
                purpose="Grab attention",
                visual_notes="Fast cuts",
                audio_notes="Beat drop",
                text_notes="Bold title",
                motion_notes="Zoom in",
            )
        ],
        confidence=0.9,
    )


def _sample_candidate(project_id: str, rank: int = 1) -> CandidateVideo:
    return CandidateVideo(
        candidate_id=f"cand-{rank}",
        project_id=project_id,
        title="Sample clip",
        source_type="public_url_reference",
        concept="Best demo",
        topic_match_score=0.82,
        visual_quality_score=0.77,
        audio_quality_score=0.71,
        motion_energy_score=0.88,
        text_relevance_score=0.69,
        reference_style_fit_score=0.84,
        source_safety_score=0.95,
        overall_score=0.8,
        recommended_rank=rank,
        reason="Strong topic fit with energetic motion.",
        highlight_reason="Peak action window matches reference rank slot pacing.",
        clip_start_sec=1.5,
        clip_end_sec=5.5,
        duration_sec=12.0,
        status="approved",
    )


def test_save_reference_video_analysis_persists_blueprint() -> None:
    board = ProjectBlackboard(project_id="proj-1", run_id="run-1", user_id="user-1")
    board.reference_blueprint = _sample_blueprint("proj-1")

    save_reference_video_analysis(board)
    stored = get_video_analyses(board.memory_context)

    assert stored["reference"] is not None
    assert stored["reference"]["hook_style"] == "question"
    assert stored["reference"]["ranking_count"] == 3
    assert VIDEO_ANALYSES_MEMORY_KEY in board.memory_context


def test_save_candidate_video_analysis_persists_scores() -> None:
    board = ProjectBlackboard(project_id="proj-2", run_id="run-2", user_id="user-2")
    candidate = _sample_candidate("proj-2")

    save_candidate_video_analysis(board, candidate, analysis_source=ANALYSIS_SOURCE_GEMINI)
    stored = get_video_analyses(board.memory_context)["candidates"][candidate.candidate_id]

    assert stored["highlight_reason"].startswith("Peak action")
    assert stored["scores"]["overall"] == 0.8
    assert stored["analysis_source"] == ANALYSIS_SOURCE_GEMINI


def test_build_edit_video_insights_orders_approved_candidates() -> None:
    board = ProjectBlackboard(project_id="proj-3", run_id="run-3", user_id="user-3")
    board.reference_blueprint = _sample_blueprint("proj-3")
    save_reference_video_analysis(board)

    second = _sample_candidate("proj-3", rank=2)
    first = _sample_candidate("proj-3", rank=1)
    first.candidate_id = "cand-first"
    second.candidate_id = "cand-second"
    board.approved_candidates = [second, first]

    save_candidate_video_analysis(board, first, analysis_source=ANALYSIS_SOURCE_GEMINI)
    save_candidate_video_analysis(board, second, analysis_source=ANALYSIS_SOURCE_LIGHTWEIGHT)

    insights = build_edit_video_insights(board)

    assert insights["reference"]["hook_style"] == "question"
    assert [entry["rank"] for entry in insights["candidates"]] == [1, 2]
    assert insights["candidates"][1]["analysis_source"] == ANALYSIS_SOURCE_LIGHTWEIGHT


def test_sync_candidate_analyses_from_approved_backfills_missing_entries() -> None:
    board = ProjectBlackboard(project_id="proj-4", run_id="run-4", user_id="user-4")
    candidate = _sample_candidate("proj-4")
    candidate.reason = "Auto-selected from learned preferences — duration match."
    board.approved_candidates = [candidate]

    sync_candidate_analyses_from_approved(board)
    stored = get_video_analyses(board.memory_context)["candidates"][candidate.candidate_id]

    assert stored["analysis_source"] == ANALYSIS_SOURCE_LIGHTWEIGHT
    assert stored["scores"]["motion_energy"] == 0.88
