import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.databricks.genie import GenieAdapter
from app.core.errors import ExternalServiceError


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response
        real_resp = Response(status_code)
        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=Request("POST", "http://x"), response=real_resp
        )
    return resp


@pytest.mark.asyncio
async def test_start_conversation_success():
    client = AsyncMock()
    client.post.return_value = _mock_response(200, {"conversation_id": "abc"})
    adapter = GenieAdapter(client, MagicMock())
    result = await adapter.start_conversation("space-1", "What?")
    assert result == {"conversation_id": "abc"}


@pytest.mark.asyncio
async def test_start_conversation_error():
    client = AsyncMock()
    client.post.return_value = _mock_response(500)
    adapter = GenieAdapter(client, MagicMock())
    with pytest.raises(ExternalServiceError, match="500"):
        await adapter.start_conversation("space-1", "What?")


@pytest.mark.asyncio
async def test_follow_up_success():
    client = AsyncMock()
    client.post.return_value = _mock_response(200, {"answer": "42"})
    adapter = GenieAdapter(client, MagicMock())
    result = await adapter.follow_up("s", "c", "Why?")
    assert result == {"answer": "42"}
