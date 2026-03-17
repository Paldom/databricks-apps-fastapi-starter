import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.config import Settings
from app.core.errors import ConfigurationError
from app.services.integrations.ai_gateway_service import AiGatewayService


@pytest.mark.asyncio
async def test_embed_delegates_to_adapter():
    adapter = MagicMock()
    adapter.embed = AsyncMock(return_value=[0.1, 0.2])
    settings = Settings(serving_endpoint_name="ep")
    service = AiGatewayService(adapter, settings, MagicMock())

    result = await service.embed("hello")

    assert result == [0.1, 0.2]
    adapter.embed.assert_awaited_once_with("ep", "hello")


@pytest.mark.asyncio
async def test_embed_raises_when_not_configured():
    adapter = MagicMock()
    settings = Settings(serving_endpoint_name=None)
    service = AiGatewayService(adapter, settings, MagicMock())

    with pytest.raises(ConfigurationError):
        await service.embed("hello")
