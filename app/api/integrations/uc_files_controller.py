import io
import os
from typing import Annotated

from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import StreamingResponse

from app.core.config import Settings
from app.core.deps import get_settings, get_uc_files_service
from app.core.errors import RequestTooLargeError
from app.core.security.rate_limit import limiter
from app.services.integrations.uc_files_service import UcFilesService

router = APIRouter(tags=["Integration: UC Files"])


@router.post("/uc/upload")
@limiter.limit("10/minute")
async def upload(
    request: Request,
    relative_path: str,
    service: Annotated[UcFilesService, Depends(get_uc_files_service)],
    s: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
):
    max_bytes = s.max_upload_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(8192)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise RequestTooLargeError(
                f"Upload exceeds maximum size of {max_bytes} bytes"
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    return await service.upload(relative_path, data)


@router.get("/uc/download")
@limiter.limit("20/minute")
async def download(
    request: Request,
    relative_path: str,
    service: Annotated[UcFilesService, Depends(get_uc_files_service)],
):
    content = await service.download(relative_path)
    stream = io.BytesIO(content)
    return StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{os.path.basename(relative_path)}"'
            )
        },
    )
