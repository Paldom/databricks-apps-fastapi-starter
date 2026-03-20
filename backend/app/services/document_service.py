from __future__ import annotations

from app.repositories.document_repository import DocumentRepository


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
            self._user_id, cursor, limit, status=status, project_id=project_id,
        )
        items = [
            {
                "id": str(d.id),
                "name": d.original_filename or "",
                "size": d.size_bytes or 0,
                "type": d.content_type or "application/octet-stream",
                "status": d.status,
                "project_id": d.project_id,
                "added_at": d.created_at,
            }
            for d in docs
        ]
        return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

    async def upload_document(
        self,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_path: str,
        project_id: str | None = None,
    ) -> dict:
        doc = await self._repo.create_document(
            owner_user_id=self._user_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
            project_id=project_id,
            status="ingested",
        )
        return {
            "id": str(doc.id),
            "name": doc.original_filename or "",
            "size": doc.size_bytes or 0,
            "type": doc.content_type or "application/octet-stream",
            "status": doc.status,
            "project_id": doc.project_id,
            "added_at": doc.created_at,
        }

    async def delete_document(self, document_id: str) -> bool:
        return await self._repo.delete_document(self._user_id, document_id)

    async def get_document_status(self, document_id: str) -> dict | None:
        doc = await self._repo.get_document(self._user_id, document_id)
        if doc is None:
            return None
        return {"id": str(doc.id), "status": doc.status}
