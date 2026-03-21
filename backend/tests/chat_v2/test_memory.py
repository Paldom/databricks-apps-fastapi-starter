"""Tests for memory bootstrapping and message conversion."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.chat.memory import (
    build_graph_input,
    convert_messages,
    has_checkpoint,
)
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


class TestConvertMessages:
    def test_user(self):
        result = convert_messages([{"role": "user", "content": "hi"}])
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "hi"

    def test_system(self):
        result = convert_messages([{"role": "system", "content": "sys"}])
        assert isinstance(result[0], SystemMessage)

    def test_assistant(self):
        result = convert_messages([{"role": "assistant", "content": "ok"}])
        assert isinstance(result[0], AIMessage)


class TestHasCheckpoint:
    @pytest.mark.asyncio
    async def test_returns_false_when_no_checkpoint(self):
        cp = MagicMock()
        cp.get.return_value = None
        assert await has_checkpoint(cp, "thread-1") is False

    @pytest.mark.asyncio
    async def test_returns_true_when_checkpoint_exists(self):
        cp = MagicMock()
        cp.get.return_value = {"some": "state"}
        assert await has_checkpoint(cp, "thread-1") is True

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self):
        cp = MagicMock()
        cp.get.side_effect = RuntimeError("boom")
        assert await has_checkpoint(cp, "thread-1") is False


class TestBuildGraphInput:
    @pytest.mark.asyncio
    async def test_bootstrap_full_history_when_no_checkpoint(self):
        cp = MagicMock()
        cp.get.return_value = None
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "how are you"},
        ]
        result = await build_graph_input(messages, "thread-new", cp)
        assert len(result["messages"]) == 3

    @pytest.mark.asyncio
    async def test_append_only_latest_user_when_checkpoint_exists(self):
        cp = MagicMock()
        cp.get.return_value = {"some": "state"}
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "how are you"},
        ]
        result = await build_graph_input(messages, "thread-existing", cp)
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "how are you"
