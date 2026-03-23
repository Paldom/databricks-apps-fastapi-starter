"""Tests for agent adapters (app, serving, Genie)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    """Run an async coroutine in a new event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_responses_result(text: str = "Hello", trace_id: str | None = None):
    """Create a mock Responses API result."""
    resp = MagicMock()
    resp.output_text = text
    resp.metadata = {"trace_id": trace_id} if trace_id else {}
    resp.databricks_output = None
    resp.to_dict.return_value = {
        "output": [
            {
                "type": "message",
                "id": "msg_test",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {"type": "output_text", "text": text, "annotations": []}
                ],
            }
        ],
    }
    return resp


def _make_completions_result(text: str = "Hello", trace_id: str | None = None):
    """Create a mock chat completions result."""
    choice = MagicMock()
    choice.message.content = text
    resp = MagicMock()
    resp.choices = [choice]
    resp.metadata = None
    if trace_id:
        resp.databricks_output = {"trace": {"trace_id": trace_id}}
    else:
        resp.databricks_output = None
    return resp


# ---------------------------------------------------------------------------
# App adapter
# ---------------------------------------------------------------------------


class TestDatabricksAppAdapter:
    def test_invoke_calls_responses_api(self):
        from app.agents.adapters.app_adapter import DatabricksAppAdapter
        from app.agents.contracts import ResponsesAgentRequest

        mock_client = MagicMock()
        mock_client.responses.create = AsyncMock(
            return_value=_make_responses_result("App response", "tr-app-1")
        )

        adapter = DatabricksAppAdapter(mock_client, "my-app")
        req = ResponsesAgentRequest(
            input=[{"role": "user", "content": "test"}]
        )

        result = _run(adapter.invoke(req))

        assert result.source == "app"
        assert result.text == "App response"
        assert result.downstream_trace_id == "tr-app-1"
        mock_client.responses.create.assert_called_once()
        call_kwargs = mock_client.responses.create.call_args
        assert call_kwargs.kwargs["model"] == "apps/my-app"


# ---------------------------------------------------------------------------
# Serving adapter
# ---------------------------------------------------------------------------


class TestServingEndpointAdapter:
    def test_invoke_responses_mode(self):
        from app.agents.adapters.serving_adapter import ServingEndpointAdapter
        from app.agents.contracts import ResponsesAgentRequest

        mock_client = MagicMock()
        mock_client.responses.create = AsyncMock(
            return_value=_make_responses_result("Serving response", "tr-svc-1")
        )

        adapter = ServingEndpointAdapter(
            mock_client, "my-endpoint", api_mode="responses"
        )
        req = ResponsesAgentRequest(
            input=[{"role": "user", "content": "test"}]
        )

        result = _run(adapter.invoke(req))

        assert result.source == "serving_endpoint"
        assert result.text == "Serving response"
        assert result.downstream_trace_id == "tr-svc-1"
        assert result.metadata["api_mode"] == "responses"

    def test_invoke_chat_completions_mode(self):
        from app.agents.adapters.serving_adapter import ServingEndpointAdapter
        from app.agents.contracts import ResponsesAgentRequest

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_completions_result("Legacy response", "tr-legacy-1")
        )

        adapter = ServingEndpointAdapter(
            mock_client, "legacy-endpoint", api_mode="chat_completions"
        )
        req = ResponsesAgentRequest(
            input=[{"role": "user", "content": "test"}]
        )

        result = _run(adapter.invoke(req))

        assert result.source == "serving_endpoint"
        assert result.text == "Legacy response"
        assert result.downstream_trace_id == "tr-legacy-1"
        assert result.metadata["api_mode"] == "chat_completions"
        # Should have legacy marker in custom_outputs
        obj = result.response.model_dump() if hasattr(result.response, "model_dump") else dict(result.response)
        assert obj.get("custom_outputs", {}).get("legacy_api_mode") == "chat_completions"


# ---------------------------------------------------------------------------
# Genie adapter
# ---------------------------------------------------------------------------


class TestGenieAdapter:
    def test_invoke_preserves_structured_outputs(self):
        from app.agents.adapters.genie_adapter import GenieAdapter
        from app.agents.contracts import ResponsesAgentRequest

        # Mock Genie SDK response
        text_obj = MagicMock()
        text_obj.content = "Revenue is $1M"
        query_obj = MagicMock()
        query_obj.query = "SELECT SUM(revenue) FROM sales"

        attachment = MagicMock()
        attachment.text = text_obj
        attachment.query = query_obj

        genie_resp = MagicMock()
        genie_resp.attachments = [attachment]
        genie_resp.conversation_id = "conv-123"

        mock_ws = MagicMock()
        mock_ws.genie.start_conversation_and_wait.return_value = genie_resp

        adapter = GenieAdapter(mock_ws, "space-xyz")
        req = ResponsesAgentRequest(
            input=[{"role": "user", "content": "What is revenue?"}]
        )

        result = _run(adapter.invoke(req))

        assert result.source == "genie"
        assert "Revenue is $1M" in result.text
        assert result.downstream_trace_id is None  # Genie doesn't provide trace IDs

        # Structured outputs preserved in custom_outputs
        resp_dict = result.response.model_dump() if hasattr(result.response, "model_dump") else dict(result.response)
        custom = resp_dict.get("custom_outputs", {})
        assert custom["backend"] == "genie"
        assert custom["sql"] == "SELECT SUM(revenue) FROM sales"
        assert custom["conversation_id"] == "conv-123"
        assert len(custom["attachments"]) == 1


class TestParseGenieResponse:
    def test_parse_with_text_and_query(self):
        from app.agents.adapters.genie_adapter import parse_genie_response

        text_obj = MagicMock()
        text_obj.content = "Answer text"
        query_obj = MagicMock()
        query_obj.query = "SELECT 1"

        attachment = MagicMock()
        attachment.text = text_obj
        attachment.query = query_obj

        rsp = MagicMock()
        rsp.attachments = [attachment]
        rsp.conversation_id = "c1"

        parsed = parse_genie_response(rsp)
        assert "Answer text" in parsed["text"]
        assert parsed["sql"] == "SELECT 1"
        assert parsed["conversation_id"] == "c1"

    def test_parse_empty_response(self):
        from app.agents.adapters.genie_adapter import parse_genie_response

        rsp = MagicMock()
        rsp.attachments = []
        rsp.conversation_id = None

        parsed = parse_genie_response(rsp)
        assert parsed["text"] == "No Genie response text"
        assert parsed["sql"] is None
