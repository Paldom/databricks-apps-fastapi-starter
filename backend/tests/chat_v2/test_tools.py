"""Tests for tool builders."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.chat.registry import SpecialistSpec
from app.chat.tools import _format_knowledge_results
from app.agents.adapters.genie_adapter import parse_genie_response


class TestParseGenieResponse:
    def test_formats_text_attachment(self):
        att = MagicMock()
        att.text = MagicMock(content="Revenue is $1M")
        att.query = None
        rsp = MagicMock(attachments=[att])
        result = parse_genie_response(rsp)
        assert "Revenue is $1M" in result["text"]

    def test_handles_empty_attachments(self):
        rsp = MagicMock(attachments=[])
        rsp.conversation_id = None
        result = parse_genie_response(rsp)
        assert result["text"] == "No Genie response text"

    def test_handles_no_attachments_attr(self):
        rsp = MagicMock(spec=[])
        del rsp.attachments
        rsp.conversation_id = None
        result = parse_genie_response(rsp)
        assert result["text"] == "No Genie response text"


class TestFormatKnowledgeResults:
    def test_formats_hits_with_source_and_score(self):
        hits = [
            {
                "chunk_text": "Some document text",
                "doc_uri": "/Volumes/a.pdf",
                "score": 0.95,
            },
            {"chunk_text": "Another doc", "file_name": "b.pdf"},
        ]
        formatted = _format_knowledge_results(hits)
        assert formatted.startswith(
            "[1] Some document text\n    Source: /Volumes/a.pdf (score: 0.95)"
        )
        assert "[2] Another doc\n    Source: b.pdf" in formatted

    def test_empty_results(self):
        assert _format_knowledge_results([]) == ""


class TestServingTool:
    @pytest.mark.asyncio
    async def test_responses_mode(self):
        ai_client = AsyncMock()
        resp = MagicMock()
        resp.output_text = "Response answer"
        resp.metadata = {}
        resp.databricks_output = None
        resp.to_dict.return_value = {
            "output": [
                {
                    "type": "message",
                    "id": "msg_test",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Response answer",
                            "annotations": [],
                        }
                    ],
                }
            ]
        }
        ai_client.responses.create.return_value = resp

        from app.chat.tools import _build_serving_tool

        spec = SpecialistSpec(
            key="serving_endpoint", description="test", kind="serving_endpoint"
        )
        settings = MagicMock()
        settings.serving_agent_endpoint = "my-endpoint"

        tool = _build_serving_tool(spec, settings, ai_client=ai_client)
        if hasattr(tool, "ainvoke"):
            result = await tool.ainvoke({"question": "hello"})
        else:
            result = await tool("hello")
        assert "Response answer" in result
