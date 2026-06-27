from typing import Any

TEST_USER_IDS: frozenset[str] = frozenset({"test-user", "list-test-user"})

TEST_PROJECT_IDS: frozenset[str] = frozenset({"proj-moe", "proj-gate", "proj-test"})

TEST_PROJECT_TITLES: frozenset[str] = frozenset(
    {
        "URL Test",
        "Test Project",
        "Listed Project",
        "Download Trace Test",
        "Review Flow Test",
        "Discovery Limit Test",
        "Approval Review Test",
        "Approval Download Test",
    }
)


def is_test_project(record: dict[str, Any]) -> bool:
    if record.get("user_id") in TEST_USER_IDS:
        return True
    if record.get("project_id") in TEST_PROJECT_IDS:
        return True
    if record.get("title") in TEST_PROJECT_TITLES:
        return True
    return False


def is_visible_saved_project(record: dict[str, Any]) -> bool:
    return not is_test_project(record)
