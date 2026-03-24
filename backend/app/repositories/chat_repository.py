from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session_model import ChatSession
from app.models.project_model import Project


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_project_chats(
        self, owner_user_id: str, project_id: str, cursor: str | None, limit: int,
    ) -> tuple[list[ChatSession], str | None, bool]:
        query = (
            select(ChatSession)
            .where(
                ChatSession.user_id == owner_user_id,
                ChatSession.project_id == project_id,
            )
            .order_by(ChatSession.updated_at.desc())
        )

        if cursor:
            query = query.where(ChatSession.id < uuid.UUID(cursor))

        query = query.limit(limit + 1)
        result = await self._session.execute(query)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = str(items[-1].id) if has_more and items else None

        return items, next_cursor, has_more

    async def create_chat(
        self, owner_user_id: str, project_id: str, title: str,
    ) -> ChatSession:
        chat = ChatSession(
            user_id=owner_user_id,
            project_id=project_id,
            title=title,
            created_by=owner_user_id,
            updated_by=owner_user_id,
        )
        self._session.add(chat)
        await self._session.flush()
        return chat

    async def update_chat(
        self, owner_user_id: str, chat_id: str, title: str | None,
    ) -> ChatSession | None:
        result = await self._session.execute(
            select(ChatSession).where(
                ChatSession.id == uuid.UUID(chat_id),
                ChatSession.user_id == owner_user_id,
            )
        )
        chat = result.scalar_one_or_none()
        if chat is None:
            return None
        if title is not None:
            chat.title = title
        chat.updated_by = owner_user_id
        await self._session.flush()
        return chat

    async def set_title_if_empty(
        self, owner_user_id: str, chat_id: str, title: str,
    ) -> ChatSession | None:
        """Set title only if the existing title is null or empty."""
        stmt = (
            update(ChatSession)
            .where(
                ChatSession.id == uuid.UUID(chat_id),
                ChatSession.user_id == owner_user_id,
                or_(ChatSession.title.is_(None), ChatSession.title == ""),
            )
            .values(title=title, updated_by=owner_user_id)
            .returning(ChatSession)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one_or_none()

    async def delete_chat(self, owner_user_id: str, chat_id: str) -> bool:
        result = await self._session.execute(
            delete(ChatSession).where(
                ChatSession.id == uuid.UUID(chat_id),
                ChatSession.user_id == owner_user_id,
            )
        )
        return result.rowcount > 0

    async def search_chats(
        self, owner_user_id: str, q: str, cursor: str | None, limit: int,
    ) -> tuple[list[dict], str | None, bool]:
        query = (
            select(
                ChatSession.id,
                ChatSession.title,
                ChatSession.project_id,
                Project.name.label("project_name"),
                ChatSession.created_at,
                ChatSession.updated_at,
            )
            .outerjoin(Project, ChatSession.project_id == Project.id)
            .where(
                ChatSession.user_id == owner_user_id,
                ChatSession.title.ilike(f"%{q}%"),
            )
            .order_by(ChatSession.updated_at.desc())
        )

        if cursor:
            query = query.where(ChatSession.id < uuid.UUID(cursor))

        query = query.limit(limit + 1)
        result = await self._session.execute(query)
        rows = result.all()

        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = str(items[-1].id) if has_more and items else None

        return (
            [
                {
                    "id": str(r.id),
                    "title": r.title or "",
                    "project_id": r.project_id or "",
                    "project_name": r.project_name or "",
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in items
            ],
            next_cursor,
            has_more,
        )

    async def get_recent_chats(
        self, owner_user_id: str, limit: int,
    ) -> list[dict]:
        query = (
            select(
                ChatSession.id,
                ChatSession.title,
                ChatSession.project_id,
                Project.name.label("project_name"),
                ChatSession.created_at,
                ChatSession.updated_at,
            )
            .outerjoin(Project, ChatSession.project_id == Project.id)
            .where(ChatSession.user_id == owner_user_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(query)
        return [
            {
                "id": str(r.id),
                "title": r.title or "",
                "project_id": r.project_id or "",
                "project_name": r.project_name or "",
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in result.all()
        ]
