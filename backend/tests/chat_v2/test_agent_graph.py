"""The real LangGraph graph must build, call a tool, answer, and keep per-thread memory."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from app.chat.agent import build_agent
from app.chat.memory import create_checkpointer


class _ToolCallingFakeModel(GenericFakeChatModel):
    """Scripted chat model that accepts tool binding (create_react_agent requires it)."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_ToolCallingFakeModel":
        return self


@tool
def echo(text: str) -> str:
    """Echo the given text."""
    return f"echo:{text}"


def _settings() -> Any:
    return type("S", (), {"langgraph_memory_backend": "inmemory"})()


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
    graph = build_agent(
        _ToolCallingFakeModel(messages=scripted),
        [echo],
        "sys",
        create_checkpointer(_settings()),
    )

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="hi")]},
        config={"configurable": {"thread_id": "user-a:thread-1"}},
    )

    messages = result["messages"]
    assert any(isinstance(m, ToolMessage) and m.content == "echo:hi" for m in messages)
    assert (
        isinstance(messages[-1], AIMessage) and messages[-1].content == "final answer"
    )


@pytest.mark.asyncio
async def test_second_turn_on_same_thread_sees_history():
    scripted = iter([AIMessage(content="one"), AIMessage(content="two")])
    checkpointer = create_checkpointer(_settings())
    graph = build_agent(
        _ToolCallingFakeModel(messages=scripted), [], "sys", checkpointer
    )
    config = {"configurable": {"thread_id": "user-a:thread-2"}}

    await graph.ainvoke({"messages": [HumanMessage(content="first")]}, config=config)
    second = await graph.ainvoke(
        {"messages": [HumanMessage(content="second")]}, config=config
    )

    contents = [m.content for m in second["messages"]]
    assert contents == ["first", "one", "second", "two"]


@pytest.mark.asyncio
async def test_checkpoint_threads_are_isolated_per_key():
    checkpointer = create_checkpointer(_settings())
    graph = build_agent(
        _ToolCallingFakeModel(messages=iter([AIMessage(content="x")])),
        [],
        "sys",
        checkpointer,
    )

    await graph.ainvoke(
        {"messages": [HumanMessage(content="secret from user a")]},
        config={"configurable": {"thread_id": "user-a:shared-id"}},
    )
    state_b = await graph.aget_state(
        {"configurable": {"thread_id": "user-b:shared-id"}}
    )

    assert not state_b.values.get("messages")
