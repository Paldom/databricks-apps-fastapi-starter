import io
from logging import Logger
from typing import cast

from databricks.sdk import WorkspaceClient

from app.core.databricks._async_bridge import run_sync
from app.core.errors import ResourceNotFoundError, UcFilesError


class UcFilesAdapter:
    def __init__(self, ws: WorkspaceClient, logger: Logger):
        self._ws = ws
        self._logger = logger

    @staticmethod
    def _vol_uri(root: str, relative_path: str) -> str:
        relative = relative_path.lstrip("/")
        return f"{root}/{relative}"

    async def upload(
        self, volume_root: str, relative_path: str, data: bytes
    ) -> int:
        """Upload bytes to a UC volume. Returns bytes written."""
        uri = self._vol_uri(volume_root, relative_path)
        self._logger.info("Uploading %d bytes to %s", len(data), uri)
        await run_sync(
            self._ws.files.upload,
            uri,
            io.BytesIO(data),
            overwrite=True,
            error_cls=UcFilesError,
        )
        return len(data)

    async def download(self, volume_root: str, relative_path: str) -> bytes:
        """Download file contents from a UC volume."""
        uri = self._vol_uri(volume_root, relative_path)
        self._logger.info("Downloading %s", uri)
        resp = await run_sync(
            self._ws.files.download,
            uri,
            error_cls=UcFilesError,
        )
        if resp.contents is None:
            raise ResourceNotFoundError(f"File not found: {relative_path}")
        return cast(bytes, resp.contents)
