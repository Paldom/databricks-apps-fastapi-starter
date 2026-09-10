"""LangGraph agent builder using ``create_react_agent``."""

from __future__ import annotations

from typing import Any

from langgraph.prebuilt import create_react_agent


def build_agent(
    model: Any,
    tools: list,
    prompt: str,
    checkpointer: Any,
) -> Any:
    """Build a compiled LangGraph agent with tools and checkpointing.

    The prebuilt agent state (``messages`` + ``remaining_steps``) is used as is;
    a custom state schema is only worth it once a node writes extra keys.
    """
    return create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        checkpointer=checkpointer,
    )
