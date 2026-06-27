import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import init_db
from app.main import app

init_db()
client = TestClient(app)


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
