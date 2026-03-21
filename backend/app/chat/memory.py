"""Short-term memory: checkpointer creation and input bootstrapping.

Thread-based memory semantics:
- First request (no checkpoint): seed the graph with full message history.
- Subsequent requests (checkpoint exists): append only the latest user message.
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger()


def create_checkpointer(settings: Settings) -> Any:
    """Create the appropriate LangGraph checkpointer based on config."""
    backend = settings.langgraph_memory_backend

    if backend == "lakebase":
        # TODO: implement Lakebase/Postgres-backed checkpointer.
        # In deployed mode this should be a hard error, not a silent fallback.
        if settings.environment not in ("development", "test"):
            raise RuntimeError(
                "Lakebase checkpointer is not yet implemented. "
                "Set LANGGRAPH_MEMORY_BACKEND=inmemory or implement the Lakebase saver."
            )
        logger.warning(
            "Lakebase checkpointer not implemented; using inmemory (dev mode)"
        )

    from langgraph.checkpoint.memory import MemorySaver

    logger.info("Using in-memory LangGraph checkpointer")
    return MemorySaver()


# ---------------------------------------------------------------------------
# Message conversion
# ---------------------------------------------------------------------------


def _convert_message(msg: dict[str, Any]) -> HumanMessage | SystemMessage | AIMessage:
    role = msg.get("role", "user")
    content = msg.get("content", "")
    if role == "system":
        return SystemMessage(content=content)
    if role == "assistant":
        return AIMessage(content=content)
    return HumanMessage(content=content)


def convert_messages(
    messages: list[dict[str, Any]],
) -> list[HumanMessage | SystemMessage | AIMessage]:
    return [_convert_message(m) for m in messages]


# ---------------------------------------------------------------------------
# Checkpoint-aware input builder
# ---------------------------------------------------------------------------


def _latest_user_message(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg
    return None


async def has_checkpoint(checkpointer: Any, thread_id: str) -> bool:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        checkpoint = await asyncio.to_thread(checkpointer.get, config)
        return checkpoint is not None
    except Exception:
        logger.debug(
            "Error checking checkpoint for thread %s", thread_id, exc_info=True
        )
        return False


async def build_graph_input(
    messages: list[dict[str, Any]],
    thread_id: str,
    checkpointer: Any,
) -> dict[str, Any]:
    """Build the input state for the agent.

    - No checkpoint: seed with full history.
    - Checkpoint exists: append only the latest user message.
    """
    has_state = await has_checkpoint(checkpointer, thread_id)

    if not has_state:
        logger.debug(
            "No checkpoint for thread %s; bootstrapping with full history", thread_id
        )
        return {"messages": convert_messages(messages)}

    latest = _latest_user_message(messages)
    if latest is None:
        logger.warning(
            "Checkpoint exists for thread %s but no user message found", thread_id
        )
        return {"messages": []}

    logger.debug(
        "Checkpoint exists for thread %s; appending latest user message", thread_id
    )
    return {"messages": convert_messages([latest])}
