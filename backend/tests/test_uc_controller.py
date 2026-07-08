from unittest.mock import MagicMock

import pytest

from app.core.databricks.uc_files import UcFilesAdapter
from app.core.errors import NotFoundError


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
    with pytest.raises(NotFoundError):
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
