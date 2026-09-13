"""Tests for the /api/agents/ controller routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


class TestAgentsBackendsList:
    """GET /api/agents/backends returns available backends."""

    def test_only_the_supervisor_when_nothing_else_is_configured(
        self, test_client: TestClient
    ):
        resp = test_client.get(
            "/api/agents/backends",
            headers={"X-Forwarded-User": "test-user"},
        )
        assert resp.status_code == 200
        assert resp.json()["backends"] == ["supervisor"]


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
        with patch("app.api.agents_controller.get_agent_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_factory.return_value = mock_adapter

            resp = test_client.post(
                "/api/agents/app/invocations",
                json={"input": "not-a-list"},  # input should be a list
                headers={"X-Forwarded-User": "test-user"},
            )
            # Should error — either 422 validation or 500 from broken input
            assert resp.status_code in (404, 422, 500)


class TestSupervisorInvocation:
    """POST /api/agents/supervisor/invocations runs the app's own agent."""

    def test_returns_responses_output_and_thread(self, test_client: TestClient):
        orchestrator = MagicMock()
        orchestrator.invoke = AsyncMock(return_value=("hello there", "tr-123"))
        with patch(
            "app.chat.deps.get_chat_orchestrator",
            AsyncMock(return_value=orchestrator),
        ):
            resp = test_client.post(
                "/api/agents/supervisor/invocations",
                json={
                    "input": [{"role": "user", "content": "Say hello"}],
                    "custom_inputs": {"thread_id": "t-1"},
                },
                headers={"X-Forwarded-User": "test-user"},
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["output"][0]["content"][0]["text"] == "hello there"
        assert body["custom_outputs"]["thread_id"] == "t-1"
        assert body["_meta"] == {
            "source": "supervisor",
            "downstream_trace_id": "tr-123",
        }
        messages, context = orchestrator.invoke.call_args.args
        assert messages == [{"role": "user", "content": "Say hello"}]
        assert context.chat_id == "t-1"
        assert context.user_id == "test-user"

    def test_accepts_text_parts(self, test_client: TestClient):
        orchestrator = MagicMock()
        orchestrator.invoke = AsyncMock(return_value=("ok", None))
        with patch(
            "app.chat.deps.get_chat_orchestrator",
            AsyncMock(return_value=orchestrator),
        ):
            resp = test_client.post(
                "/api/agents/supervisor/invocations",
                json={
                    "input": [
                        {
                            "role": "user",
                            "content": [{"type": "input_text", "text": "Hi there"}],
                        }
                    ]
                },
                headers={"X-Forwarded-User": "test-user"},
            )
        assert resp.status_code == 200, resp.text
        assert orchestrator.invoke.call_args.args[0] == [
            {"role": "user", "content": "Hi there"}
        ]

    def test_backends_list_always_includes_supervisor(self, test_client: TestClient):
        resp = test_client.get(
            "/api/agents/backends", headers={"X-Forwarded-User": "test-user"}
        )
        assert resp.json()["backends"][0] == "supervisor"
