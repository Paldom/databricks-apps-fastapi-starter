"""The real LangGraph graph must build, call a tool and answer."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from app.chat.agent import build_agent
from app.chat.orchestrator import _answer_text


class _ToolCallingFakeModel(GenericFakeChatModel):
    """Scripted chat model that accepts tool binding (create_react_agent requires it)."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_ToolCallingFakeModel":
        return self


@tool
def echo(text: str) -> str:
    """Echo the given text."""
    return f"echo:{text}"


@pytest.mark.asyncio
async def test_real_graph_calls_a_tool_and_answers():
    scripted = iter(
        [
            AIMessage(
                content="",
                tool_calls=[{"name": "echo", "args": {"text": "hi"}, "id": "call-1"}],
            ),
            AIMessage(content="final answer"),
        ]
    )
    graph = build_agent(_ToolCallingFakeModel(messages=scripted), [echo], "sys")

    result = await graph.ainvoke({"messages": [HumanMessage(content="hi")]})

    messages = result["messages"]
    assert any(isinstance(m, ToolMessage) and m.content == "echo:hi" for m in messages)
    assert _answer_text(messages) == "final answer"


def test_answer_text_skips_tool_messages_and_empty_ai_content():
    messages = [
        HumanMessage(content="q"),
        AIMessage(content="", tool_calls=[{"name": "echo", "args": {}, "id": "c1"}]),
        ToolMessage(content="tool output", tool_call_id="c1"),
        AIMessage(content=[{"type": "text", "text": "final"}]),
        ToolMessage(content="late tool output", tool_call_id="c2"),
    ]
    assert _answer_text(messages) == "final"
    assert _answer_text([HumanMessage(content="q")]) == ""
