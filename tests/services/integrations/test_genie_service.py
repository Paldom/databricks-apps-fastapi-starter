import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.integrations.genie_service import GenieService


@pytest.mark.asyncio
async def test_start_conversation_delegates():
    adapter = MagicMock()
    adapter.start_conversation = AsyncMock(return_value={"id": "c1"})
    service = GenieService(adapter, MagicMock())

    result = await service.start_conversation("space-1", "What?")

    assert result == {"id": "c1"}
    adapter.start_conversation.assert_awaited_once_with("space-1", "What?")


@pytest.mark.asyncio
async def test_follow_up_delegates():
    adapter = MagicMock()
    adapter.follow_up = AsyncMock(return_value={"answer": "42"})
    service = GenieService(adapter, MagicMock())

    result = await service.follow_up("s", "c", "Why?")

    assert result == {"answer": "42"}
    adapter.follow_up.assert_awaited_once_with("s", "c", "Why?")
