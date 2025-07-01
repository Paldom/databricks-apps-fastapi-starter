import pytest
from unittest.mock import MagicMock

from controllers.demo import upload, download
from config import Settings


class DummyUploadFile:
    def __init__(self, data: bytes):
        self._data = data

    async def read(self) -> bytes:
        return self._data


@pytest.mark.asyncio
async def test_upload_calls_files_api():
    wc = MagicMock()
    file = DummyUploadFile(b"abc")
    settings = Settings(volume_root="/root")
    result = await upload("path.txt", file, ws=wc, settings=settings)
    wc.files.upload.assert_called_once()
    assert result == {"uploaded": "path.txt", "bytes": 3}


@pytest.mark.asyncio
async def test_download_reads_file():
    wc = MagicMock()
    resp = MagicMock()
    resp.contents = b"data"
    wc.files.download.return_value = resp
    settings = Settings(volume_root="/root")
    result = download("file.txt", ws=wc, settings=settings)
    wc.files.download.assert_called_once()
    body = b"".join([chunk async for chunk in result.body_iterator])
    assert body == b"data"

