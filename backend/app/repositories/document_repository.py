from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_record_model import FileRecord


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_documents(
        self,
        owner_user_id: str,
        cursor: str | None,
        limit: int,
        status: str | None = None,
        project_id: str | None = None,
    ) -> tuple[list[FileRecord], str | None, bool]:
        query = (
            select(FileRecord)
            .where(FileRecord.user_id == owner_user_id)
            .order_by(FileRecord.created_at.desc())
        )

        if status:
            query = query.where(FileRecord.status == status)
        if project_id:
            query = query.where(FileRecord.project_id == project_id)
        if cursor:
            query = query.where(FileRecord.id < uuid.UUID(cursor))

        query = query.limit(limit + 1)
        result = await self._session.execute(query)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = str(items[-1].id) if has_more and items else None

        return items, next_cursor, has_more

    async def create_document(
        self,
        owner_user_id: str,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_path: str,
        project_id: str | None = None,
        status: str = "pending",
    ) -> FileRecord:
        doc = FileRecord(
            user_id=owner_user_id,
            project_id=project_id,
            storage_path=storage_path,
            original_filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            status=status,
            created_by=owner_user_id,
            updated_by=owner_user_id,
        )
        self._session.add(doc)
        await self._session.flush()
        return doc

    async def delete_document(self, owner_user_id: str, document_id: str) -> bool:
        result = await self._session.execute(
            delete(FileRecord).where(
                FileRecord.id == uuid.UUID(document_id),
                FileRecord.user_id == owner_user_id,
            )
        )
        return result.rowcount > 0

    async def get_document(self, owner_user_id: str, document_id: str) -> FileRecord | None:
        result = await self._session.execute(
            select(FileRecord).where(
                FileRecord.id == uuid.UUID(document_id),
                FileRecord.user_id == owner_user_id,
            )
        )
        return result.scalar_one_or_none()
