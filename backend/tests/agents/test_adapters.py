"""Tests for agent adapters (app, serving, Genie)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


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
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
    }
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
        req = ResponsesAgentRequest(input=[{"role": "user", "content": "test"}])

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

        adapter = ServingEndpointAdapter(mock_client, "my-endpoint")
        req = ResponsesAgentRequest(input=[{"role": "user", "content": "test"}])

        result = _run(adapter.invoke(req))

        assert result.source == "serving_endpoint"
        assert result.text == "Serving response"
        assert result.downstream_trace_id == "tr-svc-1"
        assert result.metadata["endpoint"] == "my-endpoint"


# ---------------------------------------------------------------------------
# Genie adapter
# ---------------------------------------------------------------------------


class TestGenieAdapter:
    @staticmethod
    def _message(status: str):
        text_obj = MagicMock()
        text_obj.content = "Revenue is $1M"
        query_obj = MagicMock()
        query_obj.query = "SELECT SUM(revenue) FROM sales"
        attachment = MagicMock()
        attachment.text = text_obj
        attachment.query = query_obj
        attachment.attachment_id = "att-1"
        message = MagicMock()
        message.attachments = [attachment]
        message.conversation_id = "conv-123"
        message.message_id = "msg-1"
        message.status = MagicMock(value=status)
        return message

    def test_invoke_polls_until_complete_and_keeps_structured_outputs(self):
        from app.agents.adapters.genie_adapter import GenieAdapter
        from app.agents.contracts import ResponsesAgentRequest

        mock_ws = MagicMock()
        mock_ws.genie.start_conversation.return_value = MagicMock(
            response=self._message("EXECUTING_QUERY")
        )
        mock_ws.genie.get_message.return_value = self._message("COMPLETED")
        mock_ws.genie.get_message_attachment_query_result.return_value = MagicMock(
            statement_response=MagicMock(result=MagicMock(data_array=[["1000000"]]))
        )
        with patch("app.agents.adapters.genie_adapter.POLL_SECONDS", 0):
            result = _run(
                GenieAdapter(mock_ws, "space-xyz").invoke(
                    ResponsesAgentRequest(
                        input=[{"role": "user", "content": "What is revenue?"}]
                    )
                )
            )

        assert result.source == "genie"
        assert "Revenue is $1M" in result.text
        outputs = result.response.custom_outputs
        assert outputs["sql"] == "SELECT SUM(revenue) FROM sales"
        assert outputs["conversation_id"] == "conv-123"
        assert outputs["message_id"] == "msg-1"
        assert outputs["status"] == "COMPLETED"
        assert outputs["rows"] == [["1000000"]]
        mock_ws.genie.get_message.assert_called_with("space-xyz", "conv-123", "msg-1")

    def test_follow_up_reuses_the_conversation_and_reports_pending(self):
        from app.agents.adapters.genie_adapter import GenieAdapter

        mock_ws = MagicMock()
        mock_ws.genie.create_message.return_value = MagicMock(
            response=self._message("EXECUTING_QUERY")
        )
        mock_ws.genie.get_message.return_value = self._message("EXECUTING_QUERY")
        with patch("app.agents.adapters.genie_adapter.POLL_SECONDS", 0):
            result = _run(
                GenieAdapter(mock_ws, "space-xyz").ask(
                    "and by region?", "conv-123", timeout=0.01
                )
            )
        mock_ws.genie.create_message.assert_called_once_with(
            "space-xyz", "conv-123", "and by region?"
        )
        mock_ws.genie.start_conversation.assert_not_called()
        assert result["status"] == "pending"
        assert result["conversation_id"] == "conv-123"


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
