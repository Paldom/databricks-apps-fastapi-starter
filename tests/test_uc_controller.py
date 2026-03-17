import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.databricks.uc_files import UcFilesAdapter
from app.core.errors import ResourceNotFoundError


@pytest.mark.asyncio
async def test_upload_returns_byte_count():
    ws = MagicMock()
    adapter = UcFilesAdapter(ws, MagicMock())
    result = await adapter.upload("/root", "path.txt", b"abc")
    ws.files.upload.assert_called_once()
    assert result == 3


@pytest.mark.asyncio
async def test_download_raises_not_found():
    ws = MagicMock()
    resp = MagicMock()
    resp.contents = None
    ws.files.download.return_value = resp
    adapter = UcFilesAdapter(ws, MagicMock())
    with pytest.raises(ResourceNotFoundError):
        await adapter.download("/root", "missing.txt")


@pytest.mark.asyncio
async def test_download_returns_content():
    ws = MagicMock()
    resp = MagicMock()
    resp.contents = b"data"
    ws.files.download.return_value = resp
    adapter = UcFilesAdapter(ws, MagicMock())
    result = await adapter.download("/root", "file.txt")
    assert result == b"data"
