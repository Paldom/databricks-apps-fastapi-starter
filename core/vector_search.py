from databricks.vector_search.client import VectorSearchClient
from databricks.vector_search.index import VectorSearchIndex

from config import settings

vector_index: VectorSearchIndex | None = None


def init_vector_index() -> None:
    """Initialise the Vector Search index connection."""
    global vector_index
    try:
        client = VectorSearchClient()
        vector_index = client.get_index(
            endpoint_name=settings.vector_search_endpoint_name,
            index_name=settings.vector_search_index_name,
        )
    except Exception:
        vector_index = None


def get_vector_index() -> VectorSearchIndex:
    if vector_index is None:
        raise RuntimeError("Vector Search index not initialised")
    return vector_index

