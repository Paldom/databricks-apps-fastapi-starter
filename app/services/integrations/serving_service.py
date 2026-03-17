from logging import Logger

import pandas as pd

from app.core.config import Settings
from app.core.databricks.serving import ServingAdapter
from app.core.errors import ConfigurationError
from app.models.integrations.serving_dto import GenericRow


class ServingService:
    def __init__(self, adapter: ServingAdapter, settings: Settings, logger: Logger):
        self._adapter = adapter
        self._settings = settings
        self._logger = logger

    async def query(self, rows: list[GenericRow]) -> dict:
        endpoint = self._settings.serving_endpoint_name
        if not endpoint:
            raise ConfigurationError("SERVING_ENDPOINT_NAME not configured")
        df = pd.DataFrame([r.model_dump() for r in rows])
        return await self._adapter.query(endpoint, df.to_dict(orient="split"))
