import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.constants.candidate_review import PLATFORM_SEARCH_HIT_POOL_KEY
from app.db import create_project, new_id
from app.schemas import AgentTrace, CandidateVideo, ReferenceBlueprint, TopicResearch
from app.services.candidate_review_service import CandidateReviewService
from app.services.web_video_fetch import DownloadAttemptResult, PlatformSearchHit


def _research_board():
    blackboard = create_project("test-user", "Review Flow Test")
    blackboard.reference_blueprint = ReferenceBlueprint(
        blueprint_id=new_id("bp"),
        project_id=blackboard.project_id,
        video_type="ranking_video",
        ranking_count=2,
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
        topic="Embarrassing moments",
        ranking_count=2,
        research_summary="Test research",
        candidate_concepts=["Concept A", "Concept B"],
        source_urls=[],
        search_results=[],
    )
    blackboard.topic = "Embarrassing moments"
    return blackboard


def test_build_status_prioritizes_awaiting_slot_over_pending_slots():
    service = CandidateReviewService()
    board = _research_board()
    service.initialize_queue(board)

    awaiting_candidate = CandidateVideo(
        candidate_id=new_id("cand"),
        project_id=board.project_id,
        title="Clip A",
        source_type="public_url_reference",
        source_url="https://www.youtube.com/watch?v=abc111",
        local_file_path="/tmp/uploads/candidates/youtube_123.mp4",
        concept="Concept A",
        topic_match_score=0.8,
        visual_quality_score=0.7,
        audio_quality_score=0.6,
        motion_energy_score=0.5,
        text_relevance_score=0.7,
        reference_style_fit_score=0.6,
        source_safety_score=0.9,
        overall_score=0.7,
        reason="Ready",
        status="selected",
        recommended_rank=1,
    )
    board.candidate_review_queue[0].current_candidate = awaiting_candidate
    board.candidate_review_queue[0].status = "awaiting_approval"

    status = service.build_status(board)

    assert status.current_status == "awaiting_approval"
    assert status.current_candidate is not None
    assert status.current_candidate.candidate_id == awaiting_candidate.candidate_id
    assert status.current_slot_rank == 1


def test_initialize_queue_creates_slots():
    service = CandidateReviewService()
    board = _research_board()
    result = service.initialize_queue(board)
    assert len(result.candidate_review_queue) == 2
    assert result.candidate_review_queue[0].concept == "Concept A"
    assert result.review_active is True


def test_approve_moves_to_next_slot():
    service = CandidateReviewService()
    board = _research_board()
    service.initialize_queue(board)

    first_candidate = CandidateVideo(
        candidate_id=new_id("cand"),
        project_id=board.project_id,
        title="Clip A",
        source_type="public_url_reference",
        source_url="https://www.youtube.com/watch?v=abc111",
        local_file_path="/tmp/a.mp4",
        concept="Concept A",
        topic_match_score=0.8,
        visual_quality_score=0.7,
        audio_quality_score=0.6,
        motion_energy_score=0.5,
        text_relevance_score=0.7,
        reference_style_fit_score=0.6,
        source_safety_score=0.9,
        overall_score=0.7,
        reason="Ready",
        status="selected",
        recommended_rank=1,
    )
    board.candidate_review_queue[0].current_candidate = first_candidate
    board.candidate_review_queue[0].status = "awaiting_approval"
    board.selected_candidates = [first_candidate]

    search_hit = PlatformSearchHit(
        url="https://www.youtube.com/watch?v=abc222",
        title="Clip B",
        platform="youtube",
        search_query="Concept B",
        score=0.9,
    )
    analyzed = first_candidate.model_copy(deep=True)
    analyzed.candidate_id = new_id("cand")
    analyzed.title = "Clip B"
    analyzed.recommended_rank = 2

    with patch.object(
        service,
        "_search_platform_hits",
        new_callable=AsyncMock,
        return_value=[search_hit],
    ), patch(
        "app.services.candidate_review_service.PlatformVideoDownloadAgent.download_single_candidate",
        new_callable=AsyncMock,
        return_value=DownloadAttemptResult(success=True, local_file_path="/tmp/b.mp4"),
    ), patch.object(
        service,
        "_analyze_candidate",
        new_callable=AsyncMock,
        return_value=analyzed,
    ), patch.object(
        service,
        "_validate_local_candidate",
        new_callable=AsyncMock,
    ) as validate_mock, patch(
        "app.services.candidate_review_service.should_use_lightweight_selection",
        return_value=(False, []),
    ):
        from app.services.video_constraint_service import VideoFitEvaluation

        validate_mock.return_value = VideoFitEvaluation(acceptable=True, fit_score=0.9)
        approved_board = asyncio.run(service.approve_candidate(board, first_candidate.candidate_id))
        result = asyncio.run(service.prepare_next_slot(approved_board))

    assert len(result.approved_candidates) == 1
    assert result.approved_candidates[0].candidate_id == first_candidate.candidate_id
    assert result.candidate_review_queue[0].status == "approved"
    assert result.candidate_review_queue[1].status == "awaiting_approval"


def test_approve_is_idempotent_for_already_approved_candidate():
    service = CandidateReviewService()
    board = _research_board()
    service.initialize_queue(board)

    candidate = CandidateVideo(
        candidate_id=new_id("cand"),
        project_id=board.project_id,
        title="Clip A",
        source_type="public_url_reference",
        source_url="https://www.youtube.com/watch?v=abc111",
        local_file_path="/tmp/a.mp4",
        concept="Concept A",
        topic_match_score=0.8,
        visual_quality_score=0.7,
        audio_quality_score=0.6,
        motion_energy_score=0.5,
        text_relevance_score=0.7,
        reference_style_fit_score=0.6,
        source_safety_score=0.9,
        overall_score=0.7,
        reason="Ready",
        status="approved",
        recommended_rank=1,
    )
    board.candidate_review_queue[0].status = "approved"
    board.candidate_review_queue[0].current_candidate = None
    board.candidate_review_queue[0].approved_candidate = candidate
    board.approved_candidates = [candidate]

    result = asyncio.run(service.approve_candidate(board, candidate.candidate_id))

    assert len(result.approved_candidates) == 1
    assert result.candidate_review_queue[0].status == "approved"


def _pool_hit(url: str, title: str, fit_score: float = 0.9) -> dict[str, object]:
    return {
        "url": url,
        "title": title,
        "platform": "tiktok" if "tiktok" in url else "youtube",
        "search_query": "Embarrassing moments shorts",
        "score": fit_score,
        "fit_score": fit_score,
        "duration_sec": None,
        "width": None,
        "height": None,
        "orientation": "mobile",
        "aspect_ratio_hint": "9:16",
        "learning_reasons": [],
    }


def test_search_platform_hits_reuses_cached_pool_without_rescanning():
    service = CandidateReviewService()
    board = _research_board()
    service.initialize_queue(board)

    pool = [
        _pool_hit("https://www.tiktok.com/@user/video/111", "Clip 1"),
        _pool_hit("https://www.tiktok.com/@user/video/222", "Clip 2"),
        _pool_hit("https://www.tiktok.com/@user/video/333", "Clip 3"),
    ]
    board.memory_context[PLATFORM_SEARCH_HIT_POOL_KEY] = pool
    slot = board.candidate_review_queue[0]

    with patch(
        "app.services.candidate_review_service.PlatformSearchSwarmAgent.execute",
        new_callable=AsyncMock,
    ) as swarm_mock:
        first_hits = asyncio.run(
            service._search_platform_hits(
                board,
                topic=board.topic or "",
                slot=slot,
                youtube_search_mode=None,
            )
        )
        slot.rejected_urls.append(str(pool[0]["url"]))
        second_hits = asyncio.run(
            service._search_platform_hits(
                board,
                topic=board.topic or "",
                slot=slot,
                youtube_search_mode=None,
            )
        )

    swarm_mock.assert_not_awaited()
    assert len(first_hits) == 3
    assert first_hits[0].url == pool[0]["url"]
    assert len(second_hits) == 2
    assert second_hits[0].url == pool[1]["url"]


def test_platform_search_pool_runs_once_on_first_slot_prepare(tmp_path):
    service = CandidateReviewService()
    board = _research_board()
    service.initialize_queue(board)

    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"fake")

    pool = [
        _pool_hit("https://www.tiktok.com/@user/video/111", "Clip 1"),
        _pool_hit("https://www.tiktok.com/@user/video/222", "Clip 2"),
        _pool_hit("https://www.tiktok.com/@user/video/333", "Clip 3"),
    ]

    async def fake_swarm_execute(current_board, **kwargs):
        current_board.memory_context["_platform_search_merged_hits"] = pool
        return current_board

    swarm_mock = MagicMock(side_effect=fake_swarm_execute)

    with patch(
        "app.services.candidate_review_service.PlatformSearchSwarmAgent.execute",
        swarm_mock,
    ), patch(
        "app.services.candidate_review_service.PlatformVideoDownloadAgent.download_single_candidate",
        new_callable=AsyncMock,
        return_value=DownloadAttemptResult(success=True, local_file_path=str(clip_path)),
    ), patch.object(
        service,
        "_analyze_candidate",
        new_callable=AsyncMock,
        side_effect=lambda current_board, candidate: candidate,
    ), patch.object(
        service,
        "_validate_local_candidate",
        new_callable=AsyncMock,
    ) as validate_mock, patch(
        "app.services.candidate_review_service.should_use_lightweight_selection",
        return_value=(False, []),
    ):
        from app.services.video_constraint_service import VideoFitEvaluation

        validate_mock.return_value = VideoFitEvaluation(acceptable=True, fit_score=0.9)

        slot_one_board = asyncio.run(service.prepare_next_slot(board))

    assert swarm_mock.call_count == 1
    assert PLATFORM_SEARCH_HIT_POOL_KEY in slot_one_board.memory_context
    assert len(slot_one_board.memory_context[PLATFORM_SEARCH_HIT_POOL_KEY]) == 3
    assert slot_one_board.selected_candidates[0].source_url in {hit["url"] for hit in pool}


def test_reject_uses_next_cached_url_without_new_search():
    service = CandidateReviewService()
    board = _research_board()
    service.initialize_queue(board)

    rejected_candidate = CandidateVideo(
        candidate_id=new_id("cand"),
        project_id=board.project_id,
        title="Bad clip",
        source_type="public_url_reference",
        source_url="https://www.youtube.com/watch?v=bad111",
        local_file_path="/tmp/bad.mp4",
        concept="Concept A",
        topic_match_score=0.4,
        visual_quality_score=0.4,
        audio_quality_score=0.4,
        motion_energy_score=0.4,
        text_relevance_score=0.4,
        reference_style_fit_score=0.4,
        source_safety_score=0.4,
        overall_score=0.4,
        reason="Not great",
        status="selected",
        recommended_rank=1,
    )
    board.candidate_review_queue[0].current_candidate = rejected_candidate
    board.candidate_review_queue[0].status = "awaiting_approval"

    pool = [
        _pool_hit("https://www.youtube.com/watch?v=bad111", "Bad clip"),
        _pool_hit("https://www.youtube.com/watch?v=good222", "Better clip"),
    ]
    board.memory_context[PLATFORM_SEARCH_HIT_POOL_KEY] = pool

    replacement = rejected_candidate.model_copy(deep=True)
    replacement.candidate_id = new_id("cand")
    replacement.source_url = "https://www.youtube.com/watch?v=good222"
    replacement.title = "Better clip"

    with patch(
        "app.services.candidate_review_service.PlatformSearchSwarmAgent.execute",
        new_callable=AsyncMock,
    ) as swarm_mock, patch(
        "app.services.candidate_review_service.PlatformVideoDownloadAgent.download_single_candidate",
        new_callable=AsyncMock,
        return_value=DownloadAttemptResult(success=True, local_file_path="/tmp/good.mp4"),
    ), patch.object(
        service,
        "_analyze_candidate",
        new_callable=AsyncMock,
        return_value=replacement,
    ), patch.object(
        service,
        "_validate_local_candidate",
        new_callable=AsyncMock,
    ) as validate_mock, patch(
        "app.services.candidate_review_service.should_use_lightweight_selection",
        return_value=(False, []),
    ):
        from app.services.video_constraint_service import VideoFitEvaluation

        validate_mock.return_value = VideoFitEvaluation(acceptable=True, fit_score=0.9)
        rejected_board = asyncio.run(service.reject_candidate(board, rejected_candidate.candidate_id))
        result = asyncio.run(service.prepare_next_slot(rejected_board))

    swarm_mock.assert_not_awaited()
    assert "https://www.youtube.com/watch?v=bad111" in result.candidate_review_queue[0].rejected_urls
    assert result.candidate_review_queue[0].status == "awaiting_approval"
    assert result.selected_candidates[0].source_url == "https://www.youtube.com/watch?v=good222"
    assert result.feedback_events
    assert result.feedback_events[-1].feedback_type == "reject"
    assert "video_preferences" in result.memory_context
