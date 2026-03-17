from logging import Logger
from typing import Any, Dict, Optional

from app.core.config import Settings
from app.core.databricks.jobs import JobsAdapter
from app.core.errors import ConfigurationError


class JobsService:
    def __init__(self, adapter: JobsAdapter, settings: Settings, logger: Logger):
        self._adapter = adapter
        self._settings = settings
        self._logger = logger

    async def run(self, params: Optional[Dict[str, Any]] = None) -> dict:
        job_id = self._settings.job_id
        if not job_id:
            raise ConfigurationError("JOB_ID not configured")
        return await self._adapter.run_and_get_output(
            job_id=int(job_id),
            notebook_params=params,
        )
