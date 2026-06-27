import asyncio
from unittest.mock import AsyncMock, patch

from app.db import create_project, new_id
from app.schemas import CandidateReviewSlot, CandidateVideo, ReferenceBlueprint, TopicResearch
from app.services.approval_service import ApprovalService
from app.services.candidate_review_service import CandidateReviewService


def _review_board():
    blackboard = create_project("test-user", "Approval Review Test")
    blackboard.reference_blueprint = ReferenceBlueprint(
        blueprint_id=new_id("bp"),
        project_id=blackboard.project_id,
        video_type="ranking_video",
        ranking_count=1,
        ranking_order="5_to_1",
        hook_duration_sec=3.0,
        average_item_duration_sec=4.0,
        outro_duration_sec=2.0,
        duration_sec=30.0,
        aspect_ratio="9:16",
        hook_style="question",
        rank_reveal_style="countdown",
        final_rank_drama_level="medium",
        confidence=0.9,
        section_order=[],
        caption_style={},
        text_overlay_style={},
        transition_style={},
        audio_style={},
        motion_style={},
        pacing_style={},
    )
    blackboard.topic_research = TopicResearch(
        project_id=blackboard.project_id,
        topic="Test topic",
        ranking_count=1,
        research_summary="Test research",
        candidate_concepts=["Concept A"],
        source_urls=[],
        search_results=[],
    )
    candidate = CandidateVideo(
        candidate_id=new_id("cand"),
        project_id=blackboard.project_id,
        title="Clip A",
        source_type="public_url_reference",
        source_url="https://www.youtube.com/watch?v=abc123",
        local_file_path="/tmp/uploads/candidates/youtube_123.mp4",
        concept="Concept A",
        topic_match_score=0.5,
        visual_quality_score=0.7,
        audio_quality_score=0.6,
        motion_energy_score=0.5,
        text_relevance_score=0.5,
        reference_style_fit_score=0.6,
        source_safety_score=0.85,
        overall_score=0.6,
        reason="Ready for approval",
        status="selected",
        recommended_rank=1,
    )
    blackboard.candidate_review_queue = [
        CandidateReviewSlot(
            slot_rank=1,
            concept="Concept A",
            status="awaiting_approval",
            current_candidate=candidate,
        )
    ]
    blackboard.review_active = True
    blackboard.selected_candidates = [candidate]
    return blackboard, candidate


def test_approve_candidate_advances_review_without_download():
    blackboard, candidate = _review_board()
    service = ApprovalService()

    with patch.object(
        CandidateReviewService,
        "approve_candidate",
        new_callable=AsyncMock,
        return_value=blackboard,
    ) as approve_mock:
        result = asyncio.run(service.approve_candidate(blackboard, candidate.candidate_id))

    approve_mock.assert_awaited_once()
    assert result.project_id == blackboard.project_id
