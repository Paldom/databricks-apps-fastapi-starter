import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.config import Settings
from app.core.errors import ConfigurationError
from app.models.integrations.serving_dto import GenericRow
from app.services.integrations.serving_service import ServingService


@pytest.mark.asyncio
async def test_query_delegates_to_adapter():
    adapter = MagicMock()
    adapter.query = AsyncMock(return_value={"predictions": [1]})
    settings = Settings(serving_endpoint_name="ep")
    service = ServingService(adapter, settings, MagicMock())

    rows = [GenericRow(id="1", data="a")]
    result = await service.query(rows)

    assert result == {"predictions": [1]}
    adapter.query.assert_awaited_once()


@pytest.mark.asyncio
async def test_query_raises_when_not_configured():
    adapter = MagicMock()
    settings = Settings(serving_endpoint_name=None)
    service = ServingService(adapter, settings, MagicMock())

    with pytest.raises(ConfigurationError, match="SERVING_ENDPOINT_NAME"):
        await service.query([])
