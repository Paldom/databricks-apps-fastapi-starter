import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.integrations.lakebase_demo_service import LakebaseDemoService


@pytest.mark.asyncio
async def test_insert_delegates():
    repo = MagicMock()
    repo.insert_demo = AsyncMock(return_value={"id": 1, "text": "hello"})
    service = LakebaseDemoService(repo, MagicMock())

    result = await service.insert("hello")

    assert result == {"id": 1, "text": "hello"}
    repo.insert_demo.assert_awaited_once_with("hello")
