import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import create_project, init_db, new_id, save_blackboard
from app.main import app
from app.schemas import CandidateVideo, ReferenceBlueprint, TopicResearch

init_db()
client = TestClient(app)


def _create_review_project():
    blackboard = create_project("test-user", "Approve API Test")
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
    blackboard.topic = "Test topic"
    blackboard.review_active = True
    candidate = CandidateVideo(
        candidate_id=new_id("cand"),
        project_id=blackboard.project_id,
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
    from app.schemas import CandidateReviewSlot

    blackboard.candidate_review_queue = [
        CandidateReviewSlot(
            slot_rank=1,
            concept="Concept A",
            status="awaiting_approval",
            current_candidate=candidate,
        )
    ]
    blackboard.selected_candidates = [candidate]
    save_blackboard(blackboard)
    return blackboard, candidate


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "missing_keys" in payload


def test_create_project():
    response = client.post("/api/projects", json={"title": "Test Project", "user_id": "test-user"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"]
    assert payload["title"] == "Test Project"


def test_list_projects():
    create_response = client.post(
        "/api/projects",
        json={"title": "Listed Project", "user_id": "list-test-user"},
    )
    project_id = create_response.json()["project_id"]

    response = client.get("/api/projects", params={"include_tests": True})
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    project_ids = [project["project_id"] for project in payload]
    assert project_id in project_ids

    filtered_response = client.get("/api/projects", params={"user_id": "list-test-user", "include_tests": True})
    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert all(project["user_id"] == "list-test-user" for project in filtered_payload)

    visible_response = client.get("/api/projects")
    visible_ids = [project["project_id"] for project in visible_response.json()]
    assert project_id not in visible_ids


def test_missing_gemini_key_message():
    settings = get_settings()
    assert settings.allow_demo_fallback is False


def test_delete_project():
    create_response = client.post(
        "/api/projects",
        json={"title": "Delete Me", "user_id": "delete-test-user"},
    )
    project_id = create_response.json()["project_id"]

    delete_response = client.delete(f"/api/projects/{project_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    get_response = client.get(f"/api/projects/{project_id}")
    assert get_response.status_code == 404

    missing_response = client.delete(f"/api/projects/{project_id}")
    assert missing_response.status_code == 404


def test_approve_candidate_accepts_empty_body():
    blackboard, candidate = _create_review_project()
    response = client.post(
        f"/api/projects/{blackboard.project_id}/candidates/{candidate.candidate_id}/approve",
        json={},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["approved_candidates"]) == 1


def test_approve_candidate_rejects_stale_candidate():
    blackboard, candidate = _create_review_project()
    blackboard.candidate_review_queue[0].current_candidate = None
    blackboard.candidate_review_queue[0].status = "pending"
    save_blackboard(blackboard)

    response = client.post(
        f"/api/projects/{blackboard.project_id}/candidates/{candidate.candidate_id}/approve",
        json={},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Candidate is not awaiting approval"
