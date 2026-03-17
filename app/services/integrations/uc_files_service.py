from logging import Logger

from app.core.config import Settings
from app.core.databricks.uc_files import UcFilesAdapter


class UcFilesService:
    def __init__(self, adapter: UcFilesAdapter, settings: Settings, logger: Logger):
        self._adapter = adapter
        self._settings = settings
        self._logger = logger

    async def upload(self, relative_path: str, data: bytes) -> dict:
        byte_count = await self._adapter.upload(
            self._settings.volume_root, relative_path, data
        )
        return {"uploaded": relative_path, "bytes": byte_count}

    async def download(self, relative_path: str) -> bytes:
        return await self._adapter.download(
            self._settings.volume_root, relative_path
        )
