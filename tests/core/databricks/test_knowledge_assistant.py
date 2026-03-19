import pytest
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient, HTTPStatusError, Request, Response

from app.core.databricks.knowledge_assistant import KnowledgeAssistantAdapter
from app.core.errors import ExternalServiceError


@pytest.mark.asyncio
async def test_ask_success():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "output": [{"type": "message", "content": [{"text": "Hello!"}]}],
        "output_text": "Hello!",
    }

    client = AsyncMock(spec=AsyncClient)
    client.post = AsyncMock(return_value=mock_response)

    adapter = KnowledgeAssistantAdapter(client, MagicMock())
    result = await adapter.ask("my-assistant", [{"role": "user", "content": "Hi"}])

    assert result["output_text"] == "Hello!"
    client.post.assert_called_once_with(
        "/serving-endpoints/responses",
        json={
            "model": "my-assistant",
            "input": [{"role": "user", "content": "Hi"}],
        },
    )


@pytest.mark.asyncio
async def test_ask_wraps_http_error():
    error_response = Response(
        status_code=500,
        request=Request("POST", "http://test/serving-endpoints/responses"),
    )
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = HTTPStatusError(
        "Server Error", request=error_response.request, response=error_response
    )
    mock_resp.response = error_response

    client = AsyncMock(spec=AsyncClient)
    client.post = AsyncMock(return_value=mock_resp)

    adapter = KnowledgeAssistantAdapter(client, MagicMock())
    with pytest.raises(ExternalServiceError, match="500"):
        await adapter.ask("my-assistant", [{"role": "user", "content": "Hi"}])


@pytest.mark.asyncio
async def test_ask_wraps_generic_error():
    client = AsyncMock(spec=AsyncClient)
    client.post = AsyncMock(side_effect=RuntimeError("connection lost"))

    adapter = KnowledgeAssistantAdapter(client, MagicMock())
    with pytest.raises(ExternalServiceError, match="connection lost"):
        await adapter.ask("my-assistant", [{"role": "user", "content": "Hi"}])
