import pytest
from fastapi.testclient import TestClient

import app.main as app_main


@pytest.fixture
def client():
    with TestClient(app_main.app) as c:
        yield c


class TestRequestSizeMiddleware:
    def test_rejects_oversized_json_payload(self, client):
        """Payload exceeding MAX_REQUEST_BODY_BYTES should return 413."""
        # Default limit is 1 MiB; send 1.5 MiB
        big_body = "x" * (1_500_000)
        resp = client.post(
            "/api/health",
            content=big_body,
            headers={
                "Content-Type": "application/json",
                "X-Forwarded-User": "test",
                "Content-Length": str(len(big_body)),
            },
        )
        assert resp.status_code == 413
        data = resp.json()
        assert data["error_code"] == "request_too_large"

    def test_allows_small_json_payload(self, client):
        """Small payloads should pass through normally."""
        resp = client.get(
            "/api/health",
            headers={"X-Forwarded-User": "test"},
        )
        assert resp.status_code == 200

    def test_rejects_oversized_content_length(self, client):
        """Request with Content-Length exceeding limit should be rejected early."""
        resp = client.post(
            "/api/health",
            content=b"small",
            headers={
                "Content-Type": "application/json",
                "X-Forwarded-User": "test",
                "Content-Length": str(2_000_000),
            },
        )
        assert resp.status_code == 413
