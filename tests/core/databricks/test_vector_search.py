import pytest
from unittest.mock import MagicMock

from app.core.databricks.vector_search import VectorSearchAdapter
from app.core.errors import VectorSearchError


@pytest.mark.asyncio
async def test_upsert_calls_index():
    index = MagicMock()
    adapter = VectorSearchAdapter(index, MagicMock())
    await adapter.upsert([{"id": "1", "values": [0.1]}])
    index.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_similarity_search_returns_results():
    index = MagicMock()
    index.similarity_search.return_value = {"results": []}
    adapter = VectorSearchAdapter(index, MagicMock())
    result = await adapter.similarity_search([0.1], ["text"], {"user": "u1"})
    assert result == {"results": []}


@pytest.mark.asyncio
async def test_upsert_wraps_error():
    index = MagicMock()
    index.upsert.side_effect = RuntimeError("fail")
    adapter = VectorSearchAdapter(index, MagicMock())
    with pytest.raises(VectorSearchError, match="fail"):
        await adapter.upsert([])


@pytest.mark.asyncio
async def test_describe_success():
    index = MagicMock()
    index.describe.return_value = {"name": "idx"}
    adapter = VectorSearchAdapter(index, MagicMock())
    result = await adapter.describe()
    assert result == {"name": "idx"}
