"""Tests for tool builders."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.chat.registry import SpecialistSpec
from app.chat.tools import _format_knowledge_results


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
        settings.tool_timeout_seconds = 5.0

        tool = _build_serving_tool(spec, settings, ai_client=ai_client)
        if hasattr(tool, "ainvoke"):
            result = await tool.ainvoke({"question": "hello"})
        else:
            result = await tool("hello")
        assert "Response answer" in result


class TestSpecialistToolsUseTheClientLayer:
    @pytest.mark.asyncio
    async def test_knowledge_assistant_tool_asks_the_endpoint(self):
        from app.chat.tools import _build_ka_endpoint_tool
        from app.core.config import Settings

        ai_client = MagicMock()
        ai_client.responses.create = AsyncMock(
            return_value=MagicMock(output_text="From the assistant")
        )
        settings = Settings(knowledge_assistant_endpoint="ka-endpoint", _env_file=None)
        tool = _build_ka_endpoint_tool(settings, ai_client=ai_client)
        assert await tool.ainvoke({"question": "what?"}) == "From the assistant"
        kwargs = ai_client.responses.create.call_args.kwargs
        assert kwargs["model"] == "ka-endpoint"
        assert kwargs["input"] == [{"role": "user", "content": "what?"}]

    @pytest.mark.asyncio
    async def test_genie_tool_records_the_conversation_for_follow_ups(self):
        from types import SimpleNamespace

        from app.chat.registry import SpecialistSpec
        from app.chat.tools import _build_genie_tool
        from app.core.config import Settings
        from app.core.context import new_turn_state

        message = SimpleNamespace(
            conversation_id="conv-9",
            id="msg-1",
            status="COMPLETED",
            attachments=[
                SimpleNamespace(text=SimpleNamespace(content="42 rows"), query=None)
            ],
        )
        ws = MagicMock()
        ws.genie.start_conversation.return_value = MagicMock(
            response=MagicMock(
                message=message, conversation_id="conv-9", message_id="msg-1"
            )
        )
        settings = Settings(genie_space_id="space-1", _env_file=None)
        spec = SpecialistSpec(key="genie", description="d", kind="genie")
        tool = _build_genie_tool(spec, settings, workspace_client=ws)
        state = new_turn_state()
        text = await tool.ainvoke(
            {"question": "how many?"}, config={"configurable": {}}
        )
        assert "42 rows" in text
        assert state["genie_conversation_id"] == "conv-9"
        ws.genie.start_conversation.assert_called_once_with("space-1", "how many?")
