from logging import Logger
from typing import Any

from app.core.config import Settings
from app.core.databricks._async_bridge import run_sync
from app.core.errors import VectorSearchError


class VectorSearchAdapter:
    def __init__(self, index: Any, logger: Logger):
        self._index = index
        self._logger = logger

    async def upsert(self, documents: list[dict]) -> None:
        """Upsert documents into the vector search index."""
        self._logger.debug("Upserting %d documents", len(documents))
        await run_sync(
            self._index.upsert,
            documents,
            error_cls=VectorSearchError,
        )

    async def similarity_search(
        self,
        query_vector: list[float],
        columns: list[str],
        filters: dict | None = None,
        num_results: int = 3,
    ) -> Any:
        """Search the vector index by query vector."""
        self._logger.debug("Searching vector index with %d results", num_results)
        return await run_sync(
            self._index.similarity_search,
            columns=columns,
            query_vector=query_vector,
            filters=filters or {},
            num_results=num_results,
            error_cls=VectorSearchError,
        )

    async def describe(self) -> Any:
        """Describe the index (used in health checks)."""
        return await run_sync(
            self._index.describe,
            error_cls=VectorSearchError,
        )


def init_vector_index(settings: Settings) -> Any:
    """Initialise the Vector Search index connection. Returns None on failure."""
    try:
        from databricks.vector_search.client import VectorSearchClient

        client = VectorSearchClient()
        return client.get_index(
            endpoint_name=settings.vector_search_endpoint_name,
            index_name=settings.vector_search_index_name,
        )
    except Exception:
        return None
