"""Tool invocation tests for the multi-agent supervisor tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.chat.registry import SpecialistSpec
from app.modules.supervisor_agent.tool import build_mas_tool

SPEC = SpecialistSpec(
    key="multi_agent_supervisor",
    description="Delegate to the hosted multi-agent supervisor.",
    kind="multi_agent_supervisor",
)


def _mock_settings(endpoint: str = "mas-endpoint") -> MagicMock:
    settings = MagicMock()
    settings.mas_endpoint = endpoint
    return settings


def _mock_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.output_text = text
    resp.metadata = {}
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
        ]
    }
    return resp


class TestMultiAgentSupervisorTool:
    def test_tool_identity_from_spec(self):
        tool = build_mas_tool(SPEC, _mock_settings(), ai_client=AsyncMock())
        assert tool.name == "multi_agent_supervisor"
        assert "supervisor" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_forwards_question_over_responses_api(self):
        ai_client = AsyncMock()
        ai_client.responses.create.return_value = _mock_response("Supervisor answer")

        tool = build_mas_tool(SPEC, _mock_settings(), ai_client=ai_client)
        result = await tool.ainvoke({"question": "hello"})

        assert "Supervisor answer" in result
        call = ai_client.responses.create.call_args
        assert call.kwargs["model"] == "mas-endpoint"
        # ResponsesAgentRequest normalizes items into typed messages.
        assert call.kwargs["input"] == [
            {"role": "user", "content": "hello", "type": "message"}
        ]

    @pytest.mark.asyncio
    async def test_error_is_returned_not_raised(self):
        ai_client = AsyncMock()
        ai_client.responses.create.side_effect = RuntimeError("endpoint down")

        tool = build_mas_tool(SPEC, _mock_settings(), ai_client=ai_client)
        result = await tool.ainvoke({"question": "hello"})

        assert result.startswith("Multi-agent supervisor error:")
        assert "endpoint down" in result
