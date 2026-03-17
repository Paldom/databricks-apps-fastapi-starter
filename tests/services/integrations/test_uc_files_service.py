import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.config import Settings
from app.services.integrations.uc_files_service import UcFilesService


@pytest.mark.asyncio
async def test_upload_delegates():
    adapter = MagicMock()
    adapter.upload = AsyncMock(return_value=5)
    settings = Settings(volume_root="/root")
    service = UcFilesService(adapter, settings, MagicMock())

    result = await service.upload("path.txt", b"hello")

    assert result == {"uploaded": "path.txt", "bytes": 5}
    adapter.upload.assert_awaited_once_with("/root", "path.txt", b"hello")


@pytest.mark.asyncio
async def test_download_delegates():
    adapter = MagicMock()
    adapter.download = AsyncMock(return_value=b"data")
    settings = Settings(volume_root="/root")
    service = UcFilesService(adapter, settings, MagicMock())

    result = await service.download("file.txt")

    assert result == b"data"
    adapter.download.assert_awaited_once_with("/root", "file.txt")
