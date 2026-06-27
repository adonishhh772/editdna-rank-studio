import pytest
from fastapi.testclient import TestClient

from app.constants.video_sources import (
    is_direct_video_url,
    is_video_url,
    validate_reference_video_url,
)
from app.db import init_db
from app.main import app

init_db()
client = TestClient(app)


def test_is_video_url_accepts_youtube():
    assert is_video_url("https://www.youtube.com/watch?v=abc123") is True


def test_is_video_url_accepts_direct_mp4():
    assert is_video_url("https://cdn.example.com/clips/demo.mp4") is True


def test_is_video_url_rejects_non_video_page():
    assert is_video_url("https://example.com/blog/post") is False


def test_is_video_url_rejects_invalid_scheme():
    assert is_video_url("ftp://example.com/video.mp4") is False


def test_is_direct_video_url_detects_video_path():
    assert is_direct_video_url("https://example.com/media/video/clip-1") is True


def test_validate_reference_video_url_strips_whitespace():
    validated = validate_reference_video_url("  https://youtu.be/abc123  ")
    assert validated == "https://youtu.be/abc123"


def test_validate_reference_video_url_raises_for_blog():
    with pytest.raises(ValueError, match="does not appear to be a video"):
        validate_reference_video_url("https://example.com/blog/article")


def test_set_reference_url_endpoint_rejects_invalid_url():
    create_response = client.post("/api/projects", json={"title": "URL Test", "user_id": "test-user"})
    project_id = create_response.json()["project_id"]

    response = client.post(
        f"/api/projects/{project_id}/reference-url",
        json={"video_url": "https://example.com/not-a-video"},
    )
    assert response.status_code == 400
    assert "does not appear to be a video" in response.json()["detail"]


def test_set_reference_url_endpoint_accepts_youtube():
    create_response = client.post("/api/projects", json={"title": "URL Test", "user_id": "test-user"})
    project_id = create_response.json()["project_id"]

    response = client.post(
        f"/api/projects/{project_id}/reference-url",
        json={"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 200
    assert response.json()["reference_video_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.json()["reference_video_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert project_response.json()["reference_video_path"] is None
