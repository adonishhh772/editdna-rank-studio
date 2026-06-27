from app.constants.project_visibility import is_test_project, is_visible_saved_project


def test_is_test_project_by_user_id() -> None:
    assert is_test_project({"user_id": "test-user", "project_id": "proj_abc", "title": "Real Title"}) is True


def test_is_test_project_by_title() -> None:
    assert is_test_project({"user_id": "default-user", "project_id": "proj_abc", "title": "URL Test"}) is True


def test_is_test_project_by_hardcoded_id() -> None:
    assert is_test_project({"user_id": "default-user", "project_id": "proj-moe", "title": "Custom"}) is True


def test_real_project_is_visible() -> None:
    record = {
        "user_id": "default-user",
        "project_id": "proj_68306b037e39",
        "title": "My Ranking Project",
    }
    assert is_visible_saved_project(record) is True
