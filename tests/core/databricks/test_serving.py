import pytest
from unittest.mock import MagicMock

from app.core.databricks.serving import ServingAdapter
from app.core.errors import ServingEndpointError


@pytest.mark.asyncio
async def test_query_success():
    ws = MagicMock()
    mock_resp = MagicMock()
    mock_resp.as_dict.return_value = {"predictions": [1, 2]}
    ws.serving_endpoints.query.return_value = mock_resp

    adapter = ServingAdapter(ws, MagicMock())
    result = await adapter.query("my-endpoint", {"columns": ["a"], "data": [[1]]})

    assert result == {"predictions": [1, 2]}
    ws.serving_endpoints.query.assert_called_once()


@pytest.mark.asyncio
async def test_query_wraps_sdk_error():
    ws = MagicMock()
    ws.serving_endpoints.query.side_effect = RuntimeError("boom")
    adapter = ServingAdapter(ws, MagicMock())
    with pytest.raises(ServingEndpointError, match="boom"):
        await adapter.query("ep", {"columns": [], "data": []})
