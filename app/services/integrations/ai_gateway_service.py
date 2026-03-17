from logging import Logger

from app.core.config import Settings
from app.core.databricks.ai_gateway import AiGatewayAdapter
from app.core.errors import ConfigurationError


class AiGatewayService:
    def __init__(self, adapter: AiGatewayAdapter, settings: Settings, logger: Logger):
        self._adapter = adapter
        self._settings = settings
        self._logger = logger

    def _endpoint(self) -> str:
        endpoint = self._settings.serving_endpoint_name
        if not endpoint:
            raise ConfigurationError("SERVING_ENDPOINT_NAME not configured")
        return endpoint

    async def embed(self, text: str) -> list[float]:
        return await self._adapter.embed(self._endpoint(), text)
