from fastapi.testclient import TestClient

from app.constants.security_headers import (
    HEADER_CONTENT_SECURITY_POLICY,
    HEADER_PERMISSIONS_POLICY,
    HEADER_REFERRER_POLICY,
    HEADER_X_CONTENT_TYPE_OPTIONS,
    HEADER_X_FRAME_OPTIONS,
    SECURITY_RESPONSE_HEADERS,
)
from app.main import app

client = TestClient(app)


def test_health_response_includes_security_headers() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    for header_name, header_value in SECURITY_RESPONSE_HEADERS.items():
        assert response.headers.get(header_name) == header_value


def test_content_security_policy_is_present_on_api_response() -> None:
    response = client.get("/api/health")

    content_security_policy = response.headers.get(HEADER_CONTENT_SECURITY_POLICY)
    assert content_security_policy is not None
    assert "default-src 'none'" in content_security_policy
    assert "frame-ancestors 'none'" in content_security_policy


def test_additional_security_headers_are_set() -> None:
    response = client.get("/api/health")

    assert response.headers.get(HEADER_X_CONTENT_TYPE_OPTIONS) == "nosniff"
    assert response.headers.get(HEADER_X_FRAME_OPTIONS) == "DENY"
    assert response.headers.get(HEADER_REFERRER_POLICY) == "strict-origin-when-cross-origin"
    assert response.headers.get(HEADER_PERMISSIONS_POLICY) is not None
