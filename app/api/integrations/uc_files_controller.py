import io
import os
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import StreamingResponse

from app.core.deps import get_uc_files_service
from app.services.integrations.uc_files_service import UcFilesService

router = APIRouter(tags=["Integration: UC Files"])


@router.post("/uc/upload")
async def upload(
    relative_path: str,
    service: Annotated[UcFilesService, Depends(get_uc_files_service)],
    file: UploadFile = File(...),
):
    data = await file.read()
    return await service.upload(relative_path, data)


@router.get("/uc/download")
async def download(
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
