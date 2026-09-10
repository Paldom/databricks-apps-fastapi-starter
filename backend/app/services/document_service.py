from __future__ import annotations

import uuid

from app.repositories.document_repository import DocumentRepository


def _to_dict(doc) -> dict:  # type: ignore[no-untyped-def]
    return {
        "id": str(doc.id),
        "name": doc.original_filename or "",
        "size": doc.size_bytes or 0,
        "type": doc.content_type or "application/octet-stream",
        "status": doc.status,
        "project_id": doc.project_id,
        "storage_path": doc.storage_path,
        "added_at": doc.created_at,
    }


class DocumentService:
    def __init__(self, repo: DocumentRepository, user_id: str) -> None:
        self._repo = repo
        self._user_id = user_id

    async def list_documents(
        self,
        cursor: str | None,
        limit: int,
        status: str | None = None,
        project_id: str | None = None,
    ) -> dict:
        docs, next_cursor, has_more = await self._repo.list_documents(
            self._user_id, cursor, limit, status=status, project_id=project_id
        )
        return {
            "items": [_to_dict(d) for d in docs],
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    async def create_pending(
        self,
        document_id: uuid.UUID,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_path: str,
    ) -> dict:
        """The record of an uploaded file; the ingestion job makes it searchable."""
        doc = await self._repo.create_document(
            owner_user_id=self._user_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
            status="pending",
            document_id=document_id,
        )
        return _to_dict(doc)

    async def get_document(self, document_id: str) -> dict | None:
        doc = await self._repo.get_document(self._user_id, document_id)
        return None if doc is None else _to_dict(doc)

    async def mark_ingested(self, document_id: str) -> None:
        await self._repo.set_status(self._user_id, document_id, "ingested")

    async def delete_document(self, document_id: str) -> bool:
        return await self._repo.delete_document(self._user_id, document_id)
