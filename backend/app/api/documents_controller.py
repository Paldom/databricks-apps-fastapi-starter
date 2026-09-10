from __future__ import annotations

from datetime import datetime

from logging import Logger
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import ConfigDict

from app.api.common.schemas import ApiModel, CursorPage, DocumentStatus
from app.core.config import Settings
from app.core.databricks.jobs import JobsAdapter
from app.core.databricks.uc_files import UcFilesAdapter
from app.core.databricks.vector_search import VectorSearchAdapter
from app.core.deps import (
    get_document_service,
    get_logger,
    get_settings,
    get_user_workspace_client,
    get_workspace_client,
)
from app.models.user_dto import CurrentUser
from app.core.deps import get_current_user
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


class Document(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "doc-1",
                "name": "Q1 Financial Report.pdf",
                "size": 2457600,
                "type": "application/pdf",
                "status": "ingested",
                "projectId": None,
                "addedAt": "2024-01-15T10:00:00Z",
            }
        }
    )

    id: str
    name: str
    size: int
    type: str
    status: DocumentStatus
    project_id: str | None = None
    added_at: datetime


class PaginatedDocuments(CursorPage[Document]):
    pass


class DocumentStatusResponse(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"id": "doc-1", "status": "ingested"}}
    )

    id: str
    status: DocumentStatus


def _to_document(d: dict) -> Document:
    return Document(
        id=d["id"],
        name=d["name"],
        size=d["size"],
        type=d["type"],
        status=d["status"],
        project_id=d.get("project_id"),
        added_at=d["added_at"],
    )


@router.get(
    "",
    operation_id="listDocuments",
    response_model=PaginatedDocuments,
)
async def list_documents(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status: DocumentStatus | None = Query(default=None),
    projectId: str | None = Query(default=None),
    service: DocumentService = Depends(get_document_service),
) -> PaginatedDocuments:
    result = await service.list_documents(
        cursor=cursor,
        limit=limit,
        status=status.value if status else None,
        project_id=projectId,
    )
    return PaginatedDocuments(
        items=[_to_document(i) for i in result["items"]],
        next_cursor=result["next_cursor"],
        has_more=result["has_more"],
    )


@router.delete(
    "/{documentId}",
    operation_id="deleteDocument",
    status_code=204,
)
async def delete_document(
    documentId: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
    service: DocumentService = Depends(get_document_service),
) -> Response:
    """Remove the file; the ingestion job then drops its chunks and index rows."""
    doc = await service.get_document(documentId)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if settings.databricks_integrations_enabled():
        await UcFilesAdapter(get_user_workspace_client(request), logger).delete(
            doc["storage_path"]
        )
        if settings.job_id:
            try:
                await JobsAdapter(get_workspace_client(request), logger).run_now(
                    int(settings.job_id)
                )
            except Exception:
                logger.warning(
                    "Could not start the ingestion job after a delete", exc_info=True
                )
    await service.delete_document(document_id=documentId)
    return Response(status_code=204)


@router.get(
    "/{documentId}/status",
    operation_id="getDocumentStatus",
    response_model=DocumentStatusResponse,
)
async def get_document_status(
    documentId: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    service: DocumentService = Depends(get_document_service),
) -> DocumentStatusResponse:
    """A pending document becomes ``ingested`` once its chunks are in the index."""
    doc = await service.get_document(documentId)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["status"] == "pending" and settings.has_vector_search_config():
        hits = await VectorSearchAdapter(
            get_workspace_client(request),
            settings.vector_search_index_name or "",
            logger,
        ).similarity_search(
            ["document_id"],
            query_text=doc["name"] or "document",
            filters={"user_id": user.id, "document_id": doc["id"]},
            num_results=1,
            timeout=settings.vector_timeout_seconds,
        )
        if hits:
            await service.mark_ingested(doc["id"])
            doc["status"] = "ingested"
    return DocumentStatusResponse(id=doc["id"], status=doc["status"])
