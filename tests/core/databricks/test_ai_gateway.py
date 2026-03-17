import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.databricks.ai_gateway import AiGatewayAdapter
from app.core.errors import AiGatewayError


@pytest.mark.asyncio
async def test_embed_success():
    client = AsyncMock()
    rsp = MagicMock()
    rsp.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
    client.embeddings.create.return_value = rsp

    adapter = AiGatewayAdapter(client, MagicMock())
    result = await adapter.embed("model-1", "hello")

    assert result == [0.1, 0.2, 0.3]
    client.embeddings.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_wraps_openai_error():
    from openai import OpenAIError

    client = AsyncMock()
    client.embeddings.create.side_effect = OpenAIError("rate limit")

    adapter = AiGatewayAdapter(client, MagicMock())
    with pytest.raises(AiGatewayError, match="rate limit"):
        await adapter.embed("model-1", "hello")
