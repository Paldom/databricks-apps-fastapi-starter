"""Inference routes require an identity; checkpoint threads are namespaced by user."""

from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as app_main
from app.chat.deps import get_chat_orchestrator
from app.core.config import settings

USER_A = {"X-Forwarded-User": "user-a", "X-Forwarded-Email": "a@example.com"}
USER_B = {"X-Forwarded-User": "user-b", "X-Forwarded-Email": "b@example.com"}


def _api_app():
    for route in app_main.app.routes:
        if getattr(route, "path", None) == "/api":
            return route.app
    raise AssertionError("Mounted /api app not found")


class _RecordingOrchestrator:
    def __init__(self) -> None:
        self.thread_ids: list[str] = []

    async def stream(self, messages, thread_id, context=None, public_thread_id=None):
        self.thread_ids.append(thread_id)
        yield {"type": "text-delta", "delta": "ok"}
        yield {"type": "done", "finish_reason": "stop", "thread_id": public_thread_id}


def test_chat_stream_requires_identity(monkeypatch):
    monkeypatch.setattr(settings, "enable_local_dev_auth_fallback", False)
    with TestClient(app_main.app) as client:
        response = client.post(
            "/api/chat/stream",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
    assert response.status_code == 401


def test_agent_invocations_require_identity(monkeypatch):
    monkeypatch.setattr(settings, "enable_local_dev_auth_fallback", False)
    with TestClient(app_main.app) as client:
        response = client.post(
            "/api/agents/genie/invocations",
            json={"input": [{"role": "user", "content": "hi"}]},
        )
    assert response.status_code == 401


def test_same_thread_id_is_namespaced_per_user(monkeypatch):
    monkeypatch.setattr(settings, "enable_chat_title_generation", False)
    recorder = _RecordingOrchestrator()
    api_app = _api_app()
    api_app.dependency_overrides[get_chat_orchestrator] = lambda: recorder
    try:
        with TestClient(app_main.app) as client:
            body = {
                "thread_id": "shared-thread",
                "messages": [{"role": "user", "content": "hi"}],
            }
            a = client.post("/api/chat/stream", json=body, headers=USER_A)
            b = client.post("/api/chat/stream", json=body, headers=USER_B)
    finally:
        api_app.dependency_overrides.clear()

    assert a.status_code == 200 and b.status_code == 200
    assert recorder.thread_ids == ["user-a:shared-thread", "user-b:shared-thread"]
    # the wire contract still reports the public id
    assert '"thread_id": "shared-thread"' in a.text
