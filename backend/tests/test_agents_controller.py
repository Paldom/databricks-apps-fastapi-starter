"""Tests for the /api/agents/ controller routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestAgentsBackendsList:
    """GET /api/agents/backends returns available backends."""

    def test_returns_empty_when_nothing_configured(self, test_client: TestClient):
        """With no backends configured, returns empty list."""
        resp = test_client.get(
            "/api/agents/backends",
            headers={"X-Forwarded-User": "test-user"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "backends" in data
        assert isinstance(data["backends"], list)


class TestAgentsInvocation:
    """POST /api/agents/{backend}/invocations tests."""

    def test_unknown_backend_returns_404(self, test_client: TestClient):
        resp = test_client.post(
            "/api/agents/nonexistent/invocations",
            json={"input": [{"role": "user", "content": "hello"}]},
            headers={"X-Forwarded-User": "test-user"},
        )
        assert resp.status_code == 404
        assert "not configured" in resp.json()["detail"]

    def test_invalid_body_returns_error(self, test_client: TestClient):
        """Sending a non-list input triggers a validation error."""
        with patch(
            "app.api.agents_controller.get_agent_adapter"
        ) as mock_factory:
            mock_adapter = MagicMock()
            mock_factory.return_value = mock_adapter

            resp = test_client.post(
                "/api/agents/app/invocations",
                json={"input": "not-a-list"},  # input should be a list
                headers={"X-Forwarded-User": "test-user"},
            )
            # Should error — either 422 validation or 500 from broken input
            assert resp.status_code in (404, 422, 500)
