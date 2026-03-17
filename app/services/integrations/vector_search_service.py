import uuid
from logging import Logger
from typing import Any

from app.core.databricks.ai_gateway import AiGatewayAdapter
from app.core.databricks.vector_search import VectorSearchAdapter
from app.core.config import Settings
from app.core.errors import ConfigurationError


class VectorSearchService:
    def __init__(
        self,
        ai_adapter: AiGatewayAdapter,
        vs_adapter: VectorSearchAdapter,
        settings: Settings,
        logger: Logger,
    ):
        self._ai = ai_adapter
        self._vs = vs_adapter
        self._settings = settings
        self._logger = logger

    def _endpoint(self) -> str:
        endpoint = self._settings.serving_endpoint_name
        if not endpoint:
            raise ConfigurationError("SERVING_ENDPOINT_NAME not configured")
        return endpoint

    async def store(self, text: str, user_id: str) -> dict:
        """Embed text and upsert to vector index. Returns id and vector."""
        vector = await self._ai.embed(self._endpoint(), text)
        doc = {
            "id": str(uuid.uuid4()),
            "values": vector,
            "metadata": {"user": user_id},
            "text": text,
        }
        await self._vs.upsert(
            [doc], timeout=float(self._settings.vector_timeout_seconds)
        )
        return {"id": doc["id"], "vector": vector}

    async def query(self, text: str, user_id: str) -> Any:
        """Embed query text and search vector index filtered by user."""
        vector = await self._ai.embed(self._endpoint(), text)
        return await self._vs.similarity_search(
            query_vector=vector,
            columns=["text"],
            filters={"user": user_id},
            num_results=3,
            timeout=float(self._settings.vector_timeout_seconds),
        )
