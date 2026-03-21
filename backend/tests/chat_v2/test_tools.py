"""Tests for tool builders."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.chat.registry import SpecialistSpec
from app.chat.tools import _format_genie_response, _format_knowledge_results


class TestFormatGenieResponse:
    def test_formats_text_attachment(self):
        att = MagicMock()
        att.text = MagicMock(content="Revenue is $1M")
        att.query = None
        rsp = MagicMock(attachments=[att])
        result = _format_genie_response(rsp)
        assert "Revenue is $1M" in result

    def test_handles_empty_attachments(self):
        rsp = MagicMock(attachments=[])
        result = _format_genie_response(rsp)
        assert result  # falls back to str(rsp)

    def test_handles_no_attachments_attr(self):
        rsp = MagicMock(spec=[])
        del rsp.attachments
        result = _format_genie_response(rsp)
        assert result


class TestFormatKnowledgeResults:
    def test_formats_hits_with_columns(self):
        results = {
            "result": {
                "column_names": ["text", "score"],
                "data_array": [
                    ["Some document text", 0.95],
                    ["Another doc", 0.85],
                ],
            }
        }
        formatted = _format_knowledge_results(results, "/Volumes/main/default")
        assert "[1]" in formatted
        assert "[2]" in formatted
        assert "Some document text" in formatted

    def test_empty_results(self):
        assert _format_knowledge_results(None, "/vol") == ""
        assert _format_knowledge_results({}, "/vol") == ""

    def test_empty_data_array(self):
        results = {"result": {"column_names": ["text"], "data_array": []}}
        assert _format_knowledge_results(results, "/vol") == ""


class TestServingTool:
    @pytest.mark.asyncio
    async def test_chat_completions_mode(self):
        ai_client = AsyncMock()
        msg = MagicMock()
        msg.content = "Answer from serving"
        choice = MagicMock()
        choice.message = msg
        ai_client.chat.completions.create.return_value = MagicMock(choices=[choice])

        from app.chat.tools import _build_serving_tool

        spec = SpecialistSpec(key="serving_endpoint", description="test", kind="serving_endpoint")
        settings = MagicMock()
        settings.serving_specialist_endpoint = "my-endpoint"
        settings.serving_specialist_api_mode = "chat_completions"

        tool = _build_serving_tool(spec, settings, ai_client=ai_client)
        # Tool may be a StructuredTool (real langchain) or raw function (stub)
        if hasattr(tool, "ainvoke"):
            result = await tool.ainvoke({"question": "hello"})
        else:
            result = await tool("hello")
        assert "Answer from serving" in result

    @pytest.mark.asyncio
    async def test_responses_mode(self):
        ai_client = AsyncMock()
        resp = MagicMock()
        resp.output_text = "Response answer"
        resp.databricks_output = None
        ai_client.responses.create.return_value = resp

        from app.chat.tools import _build_serving_tool

        spec = SpecialistSpec(key="serving_endpoint", description="test", kind="serving_endpoint")
        settings = MagicMock()
        settings.serving_specialist_endpoint = "my-endpoint"
        settings.serving_specialist_api_mode = "responses"

        tool = _build_serving_tool(spec, settings, ai_client=ai_client)
        if hasattr(tool, "ainvoke"):
            result = await tool.ainvoke({"question": "hello"})
        else:
            result = await tool("hello")
        assert "Response answer" in result
