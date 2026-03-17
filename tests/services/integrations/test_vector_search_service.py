import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.config import Settings
from app.services.integrations.vector_search_service import VectorSearchService


@pytest.mark.asyncio
async def test_store_embeds_and_upserts():
    ai_adapter = MagicMock()
    ai_adapter.embed = AsyncMock(return_value=[0.1, 0.2])
    vs_adapter = MagicMock()
    vs_adapter.upsert = AsyncMock()
    settings = Settings(serving_endpoint_name="ep")

    service = VectorSearchService(ai_adapter, vs_adapter, settings, MagicMock())
    result = await service.store("hello", "u1")

    ai_adapter.embed.assert_awaited_once_with("ep", "hello")
    vs_adapter.upsert.assert_awaited_once()
    assert result["vector"] == [0.1, 0.2]
    assert "id" in result


@pytest.mark.asyncio
async def test_query_embeds_and_searches():
    ai_adapter = MagicMock()
    ai_adapter.embed = AsyncMock(return_value=[0.1, 0.2])
    vs_adapter = MagicMock()
    vs_adapter.similarity_search = AsyncMock(return_value={"results": []})
    settings = Settings(serving_endpoint_name="ep")

    service = VectorSearchService(ai_adapter, vs_adapter, settings, MagicMock())
    result = await service.query("hello", "u1")

    assert result == {"results": []}
    vs_adapter.similarity_search.assert_awaited_once()
