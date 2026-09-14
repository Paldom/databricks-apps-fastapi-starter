"""LangGraph agent builder using ``create_react_agent``."""

from __future__ import annotations

from typing import Any

from langgraph.prebuilt import create_react_agent


def build_agent(model: Any, tools: list, prompt: str) -> Any:
    """Compiled agent over the prebuilt state (``messages`` + ``remaining_steps``).

    No checkpointer: every turn receives the stored transcript from the controller.
    """
    return create_react_agent(model=model, tools=tools, prompt=prompt)
