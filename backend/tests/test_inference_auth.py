"""Inference routes require an identity; checkpoint threads are namespaced by user."""

from __future__ import annotations

from fastapi import Depends
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
        self.chat_ids: list[str | None] = []
        self.transcripts: list[list[dict]] = []

    async def stream(self, messages, context):
        self.chat_ids.append(context.chat_id)
        self.transcripts.append(messages)
        yield {"type": "text-delta", "delta": "ok"}
        yield {"type": "done", "finish_reason": "stop", "thread_id": context.chat_id}


class _FakeChats:
    """Owned chats: user-a owns CHAT_A; everything else is unknown."""

    def __init__(self, user_id: str) -> None:
        self._user_id = user_id

    async def get_owned_chat(self, chat_id: str):
        if self._user_id == "user-a" and chat_id == CHAT_A:
            return {
                "id": CHAT_A,
                "title": "",
                "project_id": "p",
                "genie_conversation_id": None,
            }
        return None

    async def list_messages(self, chat_id, cursor, limit):
        return {
            "items": [
                {"role": "user", "content": "earlier"},
                {"role": "assistant", "content": "before"},
            ],
            "next_cursor": None,
            "has_more": False,
        }


CHAT_A = "11111111-1111-4111-8111-111111111111"


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


def test_stream_requires_an_owned_chat_and_uses_the_stored_transcript(monkeypatch):
    from app.core.deps import get_chat_service, get_current_user

    monkeypatch.setattr(settings, "enable_chat_title_generation", False)
    persisted: list[tuple] = []

    async def fake_persist(
        request, user_id, chat_id, role, content, parts, trace_id=None
    ):
        persisted.append((user_id, chat_id, role, content))

    monkeypatch.setattr("app.api.chat_stream_controller._persist", fake_persist)
    recorder = _RecordingOrchestrator()
    api_app = _api_app()
    api_app.dependency_overrides[get_chat_orchestrator] = lambda: recorder
    api_app.dependency_overrides[get_chat_service] = (
        lambda user=Depends(get_current_user): _FakeChats(user.id)
    )
    try:
        with TestClient(app_main.app) as client:
            body = {
                "thread_id": CHAT_A,
                "messages": [{"role": "user", "content": "hi"}],
            }
            a = client.post("/api/chat/stream", json=body, headers=USER_A)
            b = client.post("/api/chat/stream", json=body, headers=USER_B)
            bad = client.post(
                "/api/chat/stream",
                json={"thread_id": "not-a-uuid", "messages": body["messages"]},
                headers=USER_A,
            )
    finally:
        api_app.dependency_overrides.clear()

    assert a.status_code == 200 and '"thread_id": "%s"' % CHAT_A in a.text
    assert b.status_code == 404  # another user's chat id grants nothing
    assert bad.status_code == 422
    assert recorder.chat_ids == [CHAT_A]
    assert recorder.transcripts[0][-1] == {"role": "user", "content": "hi"}
    assert recorder.transcripts[0][0] == {"role": "user", "content": "earlier"}
    assert [(p[1], p[2]) for p in persisted] == [
        (CHAT_A, "user"),
        (CHAT_A, "assistant"),
    ]
