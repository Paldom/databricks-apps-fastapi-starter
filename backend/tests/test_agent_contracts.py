"""Tests for agent contracts, request_utils, and response_utils."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock


class TestResponseUtils:
    """response_utils helper tests."""

    def test_text_to_response_basic(self):
        from app.agents.response_utils import text_to_response

        resp = text_to_response("Hello world")
        assert resp.output is not None
        assert len(resp.output) == 1
        # The output item should be a message with text content
        item = resp.output[0]
        obj = item if isinstance(item, dict) else item.model_dump()
        assert obj["role"] == "assistant"
        assert obj["status"] == "completed"
        assert len(obj["content"]) == 1
        assert obj["content"][0]["text"] == "Hello world"

    def test_text_to_response_with_custom_outputs(self):
        from app.agents.response_utils import text_to_response

        resp = text_to_response("SQL result", custom_outputs={"sql": "SELECT 1"})
        assert resp.custom_outputs == {"sql": "SELECT 1"}

    def test_response_to_text_roundtrip(self):
        from app.agents.response_utils import text_to_response, response_to_text

        resp = text_to_response("Roundtrip test")
        text = response_to_text(resp)
        assert text == "Roundtrip test"

    def test_response_to_text_empty(self):
        from app.agents.response_utils import response_to_text
        from mlflow.types.responses import ResponsesAgentResponse

        resp = ResponsesAgentResponse(output=[])
        assert response_to_text(resp) == ""


class TestRequestUtils:
    """request_utils helper tests."""

    def test_last_user_text_basic(self):
        from app.agents.request_utils import last_user_text
        from mlflow.types.responses import ResponsesAgentRequest

        req = ResponsesAgentRequest(
            input=[
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "What is MLflow?"},
            ]
        )
        assert last_user_text(req) == "What is MLflow?"

    def test_last_user_text_multiple_messages(self):
        from app.agents.request_utils import last_user_text
        from mlflow.types.responses import ResponsesAgentRequest

        req = ResponsesAgentRequest(
            input=[
                {"role": "user", "content": "First question"},
                {"role": "assistant", "content": "Answer"},
                {"role": "user", "content": "Follow-up"},
            ]
        )
        assert last_user_text(req) == "Follow-up"

    def test_last_user_text_no_user_messages(self):
        from app.agents.request_utils import last_user_text
        from mlflow.types.responses import ResponsesAgentRequest

        req = ResponsesAgentRequest(
            input=[{"role": "system", "content": "System only"}]
        )
        assert last_user_text(req) == ""


class TestAgentInvocationResult:
    """AgentInvocationResult model tests."""

    def test_basic_construction(self):
        from app.agents.contracts import AgentInvocationResult
        from app.agents.response_utils import text_to_response

        resp = text_to_response("test")
        result = AgentInvocationResult(
            source="test_backend",
            response=resp,
            text="test",
            downstream_trace_id="tr-123",
        )
        assert result.source == "test_backend"
        assert result.text == "test"
        assert result.downstream_trace_id == "tr-123"
        assert result.metadata == {}

    def test_with_metadata(self):
        from app.agents.contracts import AgentInvocationResult
        from app.agents.response_utils import text_to_response

        result = AgentInvocationResult(
            source="genie",
            response=text_to_response("hi"),
            text="hi",
            metadata={"space_id": "abc"},
        )
        assert result.metadata["space_id"] == "abc"
