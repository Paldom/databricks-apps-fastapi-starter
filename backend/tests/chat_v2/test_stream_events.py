"""Event translation, part accumulation and the heartbeat/deadline wrapper."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.messages import ToolMessage

from app.api.chat_stream_controller import _with_heartbeat
from app.chat.orchestrator import _translate_event
from app.chat.parts import TurnAccumulator


def _chunk(content="", tool_call_chunks=None):
    return SimpleNamespace(content=content, tool_call_chunks=tool_call_chunks or [])


def test_tool_call_deltas_keep_their_id_across_chunks():
    ids: dict = {}
    first = {
        "event": "on_chat_model_stream",
        "data": {
            "chunk": _chunk(
                tool_call_chunks=[
                    {"id": "call_1", "index": 0, "name": "echo", "args": ""}
                ]
            )
        },
    }
    later = {
        "event": "on_chat_model_stream",
        "data": {
            "chunk": _chunk(
                tool_call_chunks=[
                    {"id": None, "index": 0, "name": None, "args": '{"text": "hi"}'}
                ]
            )
        },
    }
    out = _translate_event(first, ids) + _translate_event(later, ids)
    assert out == [
        {"type": "tool-call-begin", "tool_call_id": "call_1", "tool_name": "echo"},
        {
            "type": "tool-call-delta",
            "tool_call_id": "call_1",
            "args_delta": '{"text": "hi"}',
        },
    ]
    # a new model call starts a new index space
    assert _translate_event({"event": "on_chat_model_start", "data": {}}, ids) == []
    assert ids["ids"] == {}


def test_tool_results_come_from_the_tools_node():
    event = {
        "event": "on_chain_end",
        "name": "tools",
        "data": {
            "output": {
                "messages": [
                    ToolMessage(
                        content="echo:hi", tool_call_id="call_1", status="error"
                    )
                ]
            }
        },
    }
    assert _translate_event(event, {}) == [
        {
            "type": "tool-result",
            "tool_call_id": "call_1",
            "result": "echo:hi",
            "is_error": True,
        }
    ]


def test_accumulator_builds_ordered_parts():
    turn = TurnAccumulator()
    for event in [
        {"type": "text-delta", "delta": "Let me "},
        {"type": "text-delta", "delta": "check."},
        {
            "type": "tool-call-begin",
            "tool_call_id": "c1",
            "tool_name": "knowledge_assistant",
        },
        {"type": "tool-call-delta", "tool_call_id": "c1", "args_delta": '{"question":'},
        {"type": "tool-call-delta", "tool_call_id": "c1", "args_delta": ' "x"}'},
        {
            "type": "tool-result",
            "tool_call_id": "c1",
            "result": "[1] x",
            "is_error": False,
        },
        {"type": "text-delta", "delta": "Answer."},
        {"type": "done", "finish_reason": "stop"},
    ]:
        turn.feed(event)
    assert [p["type"] for p in turn.parts] == ["text", "tool-call", "text"]
    assert turn.parts[1]["args"] == {"question": "x"}
    assert turn.parts[1]["result"] == "[1] x"
    assert turn.text == "Let me check.Answer."


@pytest.mark.asyncio
async def test_heartbeat_while_the_producer_is_quiet(monkeypatch):
    monkeypatch.setattr("app.api.chat_stream_controller.HEARTBEAT_SECONDS", 0.05)

    async def slow():
        await asyncio.sleep(0.12)
        yield {"type": "text-delta", "delta": "hi"}

    events = [e async for e in _with_heartbeat(slow(), deadline=5)]
    assert events[-1] == {"type": "text-delta", "delta": "hi"}
    assert events[0] == {"type": "heartbeat"}


@pytest.mark.asyncio
async def test_deadline_raises_timeout(monkeypatch):
    monkeypatch.setattr("app.api.chat_stream_controller.HEARTBEAT_SECONDS", 0.05)

    async def never():
        await asyncio.sleep(10)
        yield {"type": "done"}

    with pytest.raises(TimeoutError):
        async for _ in _with_heartbeat(never(), deadline=0.1):
            pass
