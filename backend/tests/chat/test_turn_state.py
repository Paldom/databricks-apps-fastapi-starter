"""Per-turn state written by tools in their own tasks reaches the controller."""

from __future__ import annotations

import asyncio

import pytest

from app.core.context import new_turn_state, record_turn


@pytest.mark.asyncio
async def test_turn_state_is_shared_with_child_tasks():
    state = new_turn_state()

    async def tool() -> None:  # LangGraph runs tools in their own tasks
        record_turn(genie_conversation_id="conv-1")

    task = asyncio.create_task(
        tool()
    )  # kept in a variable so it is not collected early
    await task
    assert state == {"genie_conversation_id": "conv-1"}


def test_record_turn_without_a_turn_is_a_no_op():
    record_turn(trace_id="t")  # e.g. a tool invoked outside a chat turn
