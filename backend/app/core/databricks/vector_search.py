"""Similarity search on an AI Search (Vector Search) index through the workspace client.

The SDK call authenticates with the app's OAuth identity; nothing is resolved at
startup, so a missing index only fails the request that needs it.
"""

from __future__ import annotations

import json
from logging import Logger
from typing import Any

from databricks.sdk import WorkspaceClient

from app.core.databricks._async_bridge import run_sync
from app.core.errors import ExternalServiceError
from app.core.observability import get_tracer, tag_exception

_tracer = get_tracer()


class VectorSearchAdapter:
    def __init__(self, workspace: WorkspaceClient, index_name: str, logger: Logger):
        self._workspace = workspace
        self._index_name = index_name
        self._logger = logger

    async def similarity_search(
        self,
        columns: list[str],
        *,
        query_text: str | None = None,
        query_vector: list[float] | None = None,
        filters: dict[str, Any] | None = None,
        num_results: int = 3,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Nearest rows as dicts keyed by column name (plus ``score``).

        ``query_text`` uses the index's own embedding model (hybrid search); a
        ``query_vector`` is for indexes without managed embeddings.
        """
        with _tracer.start_as_current_span(
            "dependency.vector.search",
            attributes={
                "dependency": "vector",
                "operation": "search",
                "vector.num_results": num_results,
            },
        ) as span:
            try:
                response = await run_sync(
                    self._workspace.vector_search_indexes.query_index,
                    index_name=self._index_name,
                    columns=columns,
                    query_text=query_text,
                    query_type="HYBRID" if query_text else None,
                    query_vector=query_vector,
                    filters_json=json.dumps(filters) if filters else None,
                    num_results=num_results,
                    error_cls=ExternalServiceError,
                    timeout=timeout,
                )
                span.set_attribute("result", "ok")
                return _rows(response)
            except Exception as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise


def _rows(response: Any) -> list[dict[str, Any]]:
    manifest = getattr(response, "manifest", None)
    names = [c.name for c in (getattr(manifest, "columns", None) or [])]
    result = getattr(response, "result", None)
    rows: list[dict[str, Any]] = []
    for row in getattr(result, "data_array", None) or []:
        hit = dict(zip(names, row))
        if len(row) == len(names) + 1:  # the API appends the score column
            hit["score"] = row[-1]
        rows.append(hit)
    return rows
