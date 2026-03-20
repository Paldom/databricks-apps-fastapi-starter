from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import ConfigDict

from app.api.common.schemas import ApiModel, CursorPage, DocumentStatus
from app.core.deps import get_document_service
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


@router.post(
    "",
    operation_id="uploadDocument",
    response_model=Document,
    status_code=201,
)
async def upload_document(
    file: UploadFile = File(...),
    projectId: str | None = Form(default=None),
    service: DocumentService = Depends(get_document_service),
) -> Document:
    content = await file.read()
    storage_path = f"/uploads/{file.filename}"
    result = await service.upload_document(
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        storage_path=storage_path,
        project_id=projectId,
    )
    return _to_document(result)


@router.delete(
    "/{documentId}",
    operation_id="deleteDocument",
    status_code=204,
)
async def delete_document(
    documentId: str,
    service: DocumentService = Depends(get_document_service),
) -> Response:
    deleted = await service.delete_document(document_id=documentId)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(status_code=204)


@router.get(
    "/{documentId}/status",
    operation_id="getDocumentStatus",
    response_model=DocumentStatusResponse,
)
async def get_document_status(
    documentId: str,
    service: DocumentService = Depends(get_document_service),
) -> DocumentStatusResponse:
    result = await service.get_document_status(document_id=documentId)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentStatusResponse(id=result["id"], status=result["status"])
