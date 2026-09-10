from unittest.mock import MagicMock

import pytest

from app.core.databricks.vector_search import VectorSearchAdapter
from app.core.errors import ExternalServiceError


def _response(columns, rows):
    manifest = MagicMock(columns=[MagicMock(name=c) for c in columns])
    for col, name in zip(manifest.columns, columns):
        col.name = name
    return MagicMock(manifest=manifest, result=MagicMock(data_array=rows))


@pytest.mark.asyncio
async def test_similarity_search_maps_rows_and_score():
    workspace = MagicMock()
    workspace.vector_search_indexes.query_index.return_value = _response(
        ["chunk_text", "doc_uri"], [["hello", "/Volumes/a.pdf", 0.9]]
    )
    hits = await VectorSearchAdapter(
        workspace, "cat.sch.idx", MagicMock()
    ).similarity_search(
        [0.1], ["chunk_text", "doc_uri"], {"user_id": "u1"}, num_results=2
    )
    assert hits == [{"chunk_text": "hello", "doc_uri": "/Volumes/a.pdf", "score": 0.9}]
    kwargs = workspace.vector_search_indexes.query_index.call_args.kwargs
    assert kwargs["index_name"] == "cat.sch.idx"
    assert kwargs["filters_json"] == '{"user_id": "u1"}'
    assert kwargs["num_results"] == 2


@pytest.mark.asyncio
async def test_similarity_search_wraps_errors():
    workspace = MagicMock()
    workspace.vector_search_indexes.query_index.side_effect = RuntimeError(
        "index missing"
    )
    with pytest.raises(ExternalServiceError, match="index missing"):
        await VectorSearchAdapter(workspace, "idx", MagicMock()).similarity_search(
            [0.1], ["chunk_text"]
        )
