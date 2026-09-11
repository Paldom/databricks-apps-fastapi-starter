"""Inference routes require an identity; checkpoint threads are namespaced by user."""

from __future__ import annotations

import pytest
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
    """Owned chats: user-a owns CHAT_A; everything else is unknown. Records writes."""

    writes: list[tuple] = []

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

    async def recent_transcript(self, chat_id, limit):
        return [
            {"role": "user", "content": "earlier"},
            {"role": "assistant", "content": "before"},
        ]

    async def add_message(self, chat_id, role, content, parts=None, trace_id=None):
        _FakeChats.writes.append((self._user_id, chat_id, role, content))
        return "m"

    async def set_genie_conversation(self, chat_id, conversation_id):
        _FakeChats.writes.append((self._user_id, chat_id, "genie", conversation_id))


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
    from contextlib import asynccontextmanager

    monkeypatch.setattr(settings, "enable_chat_title_generation", False)
    _FakeChats.writes = []

    @asynccontextmanager
    async def fake_chats(request, user_id):
        yield _FakeChats(user_id)

    monkeypatch.setattr("app.api.chat_stream_controller._chats", fake_chats)
    recorder = _RecordingOrchestrator()
    api_app = _api_app()
    api_app.dependency_overrides[get_chat_orchestrator] = lambda: recorder
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
    assert recorder.transcripts[0][0] == {"role": "user", "content": "earlier"}
    assert recorder.transcripts[0][-1] == {"role": "user", "content": "hi"}
    # the assistant message is stored before `done` is sent, both for the owning user
    assert [(w[1], w[2]) for w in _FakeChats.writes] == [
        (CHAT_A, "user"),
        (CHAT_A, "assistant"),
    ]
    assert a.text.strip().splitlines()[-1].startswith('{"type": "done"')


@pytest.mark.asyncio
async def test_stream_rejects_a_second_turn_on_the_same_chat(monkeypatch):
    """The chat is reserved while a turn runs (the test clients buffer responses, so the
    route is driven directly)."""
    import asyncio
    from contextlib import asynccontextmanager

    from app.api import chat_stream_controller as ctrl
    from app.models.user_dto import CurrentUser

    monkeypatch.setattr(settings, "enable_chat_title_generation", False)
    _FakeChats.writes = []

    @asynccontextmanager
    async def fake_chats(request, user_id):
        yield _FakeChats(user_id)

    release = asyncio.Event()

    class _SlowOrchestrator:
        async def stream(self, messages, context):
            yield {"type": "text-delta", "delta": "thinking"}
            await release.wait()
            yield {
                "type": "done",
                "finish_reason": "stop",
                "thread_id": context.chat_id,
            }

    monkeypatch.setattr(ctrl, "_chats", fake_chats)
    user = CurrentUser(id="user-a", email="a@example.com")
    body = ctrl.ChatStreamRequest(
        thread_id=CHAT_A, messages=[ctrl.ChatStreamMessage(role="user", content="hi")]
    )

    async def start():
        response = await ctrl.chat_stream(
            body, request=object(), user=user, orchestrator=_SlowOrchestrator()
        )
        return response.body_iterator

    first = await start()
    assert '"text-delta"' in await first.__anext__()  # the first turn is running
    second = [line async for line in await start()]
    release.set()
    rest = [line async for line in first]

    assert len(second) == 1 and '"code": "busy"' in second[0]
    assert rest[-1].startswith('{"type": "done"')
    # the rejected turn stored nothing; the first one stored its user and assistant rows
    assert [w[2] for w in _FakeChats.writes] == ["user", "assistant"]
