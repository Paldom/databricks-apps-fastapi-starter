"""LangGraph agent builder using ``create_react_agent``."""

from __future__ import annotations

from typing import Annotated, Any, Sequence, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent


class ChatState(TypedDict, total=False):
    """Minimal state for the supervisor agent."""

    messages: Annotated[Sequence[AnyMessage], add_messages]
    custom_inputs: dict[str, Any]
    custom_outputs: dict[str, Any]


def build_agent(
    model: Any,
    tools: list,
    prompt: str,
    checkpointer: Any,
) -> Any:
    """Build a compiled LangGraph agent with tools and checkpointing."""
    return create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        checkpointer=checkpointer,
        state_schema=ChatState,
    )
