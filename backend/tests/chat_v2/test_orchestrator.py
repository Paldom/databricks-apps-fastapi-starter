"""Tests for the ChatOrchestrator event translation."""

from __future__ import annotations

from app.chat.orchestrator import _translate_event


class TestTranslateEvent:
    def test_text_delta(self):
        chunk = type("C", (), {"content": "hello", "tool_call_chunks": None})()
        event = {
            "event": "on_chat_model_stream",
            "data": {"chunk": chunk},
            "metadata": {"langgraph_node": "agent"},
        }
        result = _translate_event(event, set())
        assert result == [{"type": "text-delta", "delta": "hello"}]

    def test_empty_content_ignored(self):
        chunk = type("C", (), {"content": "", "tool_call_chunks": None})()
        event = {
            "event": "on_chat_model_stream",
            "data": {"chunk": chunk},
            "metadata": {"langgraph_node": "agent"},
        }
        assert _translate_event(event, set()) == []

    def test_tool_call_begin(self):
        tc = {"id": "tc1", "name": "genie", "args": None}
        chunk = type("C", (), {"content": None, "tool_call_chunks": [tc]})()
        event = {
            "event": "on_chat_model_stream",
            "data": {"chunk": chunk},
            "metadata": {"langgraph_node": "agent"},
        }
        result = _translate_event(event, set())
        assert len(result) == 1
        assert result[0]["type"] == "tool-call-begin"
        assert result[0]["tool_name"] == "genie"

    def test_tool_call_begin_only_once(self):
        tc = {"id": "tc1", "name": "genie", "args": None}
        chunk = type("C", (), {"content": None, "tool_call_chunks": [tc]})()
        event = {
            "event": "on_chat_model_stream",
            "data": {"chunk": chunk},
            "metadata": {"langgraph_node": "agent"},
        }
        seen: set[str] = set()
        _translate_event(event, seen)
        result = _translate_event(event, seen)
        assert result == []  # no duplicate begin

    def test_tool_call_delta(self):
        tc = {"id": "tc1", "name": None, "args": '{"q":'}
        chunk = type("C", (), {"content": None, "tool_call_chunks": [tc]})()
        event = {
            "event": "on_chat_model_stream",
            "data": {"chunk": chunk},
            "metadata": {"langgraph_node": "agent"},
        }
        result = _translate_event(event, set())
        assert len(result) == 1
        assert result[0]["type"] == "tool-call-delta"

    def test_non_agent_node_filtered(self):
        chunk = type("C", (), {"content": "hello", "tool_call_chunks": None})()
        event = {
            "event": "on_chat_model_stream",
            "data": {"chunk": chunk},
            "metadata": {"langgraph_node": "tool_node"},
        }
        assert _translate_event(event, set()) == []

    def test_unknown_event_type_ignored(self):
        event = {"event": "on_chain_start", "data": {}, "metadata": {}}
        assert _translate_event(event, set()) == []

    def test_missing_chunk_handled(self):
        event = {
            "event": "on_chat_model_stream",
            "data": {},
            "metadata": {"langgraph_node": "agent"},
        }
        assert _translate_event(event, set()) == []
