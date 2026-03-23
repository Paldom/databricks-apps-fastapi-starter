"""Knowledge file upload route.

Upload writes documents to a UC volume under a deterministic per-user path.
The file-arrival-triggered ingestion job discovers new files automatically.

The Knowledge Assistant is invoked only via the chat orchestrator — the
frontend must not call it directly.
"""

from __future__ import annotations

import base64
import re
import uuid
from logging import Logger
from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel

from app.core.config import Settings
from app.core.databricks.uc_files import UcFilesAdapter
from app.core.deps import get_current_user, get_logger, get_settings, get_workspace_client
from app.core.errors import ConfigurationError, RequestTooLargeError
from app.core.integrations import databricks_integrations_disabled_message
from app.models.user_dto import CurrentUser

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".ppt", ".pptx"}
UPLOAD_SUBDIR = "knowledge/uploads"

_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _encode_user_id(user_id: str) -> str:
    """Base64url-encode user_id without padding for path safety."""
    return base64.urlsafe_b64encode(user_id.encode("utf-8")).decode("ascii").rstrip("=")


def _safe_filename(filename: str) -> str:
    name = PurePosixPath(filename or "").name.strip()
    if not name:
        raise ValueError("Filename is required")
    name = _FILENAME_SAFE.sub("-", name).lstrip("._-")
    if not name:
        raise ValueError("Filename is invalid after sanitization")
    return name[:200]


def _require_databricks(settings: Settings) -> None:
    if not settings.databricks_integrations_enabled():
        raise ConfigurationError(databricks_integrations_disabled_message())


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class KnowledgeFileUploadResponse(BaseModel):
    document_id: str
    relative_path: str
    full_path: str
    size_bytes: int
    status: str = "uploaded"


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@router.post("/files", response_model=KnowledgeFileUploadResponse, status_code=201)
async def upload_knowledge_file(
    request: Request,
    file: UploadFile = File(...),
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
    logger: Annotated[Logger, Depends(get_logger)] = None,  # type: ignore[assignment]
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> KnowledgeFileUploadResponse:
    _require_databricks(settings)

    filename = _safe_filename(file.filename or "")
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ConfigurationError(
            f"Unsupported file type: {suffix}. "
            f"Allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}"
        )

    # Read with size enforcement
    max_bytes = settings.max_upload_bytes
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
    payload = b"".join(chunks)

    document_id = str(uuid.uuid4())
    encoded_uid = _encode_user_id(current_user.id)
    relative_path = f"{UPLOAD_SUBDIR}/{encoded_uid}/{document_id}__{filename}"

    adapter = UcFilesAdapter(get_workspace_client(request), logger)
    uploaded = await adapter.upload(
        settings.volume_root, relative_path, payload, overwrite=False,
    )

    full_path = f"{settings.volume_root.rstrip('/')}/{relative_path}"
    logger.info("Knowledge file uploaded: %s (%d bytes)", full_path, uploaded)

    return KnowledgeFileUploadResponse(
        document_id=document_id,
        relative_path=relative_path,
        full_path=full_path,
        size_bytes=uploaded,
    )
