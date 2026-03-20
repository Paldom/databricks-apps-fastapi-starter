from logging import Logger
from typing import Any

from app.core.config import Settings
from app.core.databricks._async_bridge import run_sync
from app.core.errors import ExternalServiceError
from app.core.observability import get_tracer, tag_exception


_tracer = get_tracer()


class VectorSearchAdapter:
    def __init__(self, index: Any, logger: Logger):
        self._index = index
        self._logger = logger

    async def upsert(self, documents: list[dict], *, timeout: float | None = None) -> None:
        """Upsert documents into the vector search index."""
        with _tracer.start_as_current_span(
            "dependency.vector.upsert",
            attributes={
                "dependency": "vector",
                "operation": "upsert",
                "vector.doc_count": len(documents),
            },
        ) as span:
            self._logger.debug("Upserting %d documents", len(documents))
            try:
                await run_sync(
                    self._index.upsert,
                    documents,
                    error_cls=ExternalServiceError,
                    timeout=timeout,
                )
                span.set_attribute("result", "ok")
            except Exception as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise

    async def similarity_search(
        self,
        query_vector: list[float],
        columns: list[str],
        filters: dict | None = None,
        num_results: int = 3,
        *,
        timeout: float | None = None,
    ) -> Any:
        """Search the vector index by query vector."""
        with _tracer.start_as_current_span(
            "dependency.vector.search",
            attributes={
                "dependency": "vector",
                "operation": "search",
                "vector.num_results": num_results,
            },
        ) as span:
            self._logger.debug(
                "Searching vector index with %d results", num_results
            )
            try:
                result = await run_sync(
                    self._index.similarity_search,
                    columns=columns,
                    query_vector=query_vector,
                    filters=filters or {},
                    num_results=num_results,
                    error_cls=ExternalServiceError,
                    timeout=timeout,
                )
                span.set_attribute("result", "ok")
                return result
            except Exception as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise

    async def describe(self) -> Any:
        """Describe the index (used in health checks)."""
        return await run_sync(
            self._index.describe,
            error_cls=ExternalServiceError,
        )


def init_vector_index(settings: Settings) -> Any:
    """Initialise the Vector Search index connection."""
    from databricks.vector_search.client import VectorSearchClient

    client = VectorSearchClient()
    return client.get_index(
        endpoint_name=settings.vector_search_endpoint_name,
        index_name=settings.vector_search_index_name,
    )
