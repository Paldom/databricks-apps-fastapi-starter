from __future__ import annotations

import uuid

from app.core.pagination import decode_cursor, encode_cursor
from sqlalchemy import tuple_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session_model import ChatSession
from app.models.project_model import Project


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_projects(
        self,
        owner_user_id: str,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[dict], str | None, bool]:
        # Count chats per project via subquery
        chat_count_sq = (
            select(
                ChatSession.project_id,
                func.count().label("chat_count"),
            )
            .where(ChatSession.project_id.is_not(None))
            .group_by(ChatSession.project_id)
            .subquery()
        )

        query = (
            select(
                Project.id,
                Project.name,
                Project.created_at,
                func.coalesce(chat_count_sq.c.chat_count, 0).label("chat_count"),
            )
            .outerjoin(chat_count_sq, Project.id == chat_count_sq.c.project_id)
            .where(Project.owner_user_id == owner_user_id)
            .order_by(Project.created_at.desc(), Project.id.desc())
        )

        if cursor:
            stamp, row_id = decode_cursor(cursor)
            query = query.where(
                tuple_(Project.created_at, Project.id) < (stamp, row_id)
            )

        query = query.limit(limit + 1)
        result = await self._session.execute(query)
        rows = result.all()

        has_more = len(rows) > limit
        items = rows[:limit]

        next_cursor = (
            encode_cursor(items[-1].created_at, items[-1].id)
            if has_more and items
            else None
        )

        return (
            [
                {
                    "id": r.id,
                    "name": r.name,
                    "created_at": r.created_at,
                    "chat_count": r.chat_count,
                }
                for r in items
            ],
            next_cursor,
            has_more,
        )

    async def create_project(self, owner_user_id: str, name: str) -> Project:
        project = Project(
            id=f"proj-{uuid.uuid4().hex[:12]}",
            owner_user_id=owner_user_id,
            name=name,
        )
        self._session.add(project)
        await self._session.flush()
        return project

    async def update_project(
        self,
        owner_user_id: str,
        project_id: str,
        name: str,
    ) -> Project | None:
        result = await self._session.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_user_id == owner_user_id,
            )
        )
        project = result.scalar_one_or_none()
        if project is None:
            return None
        project.name = name
        await self._session.flush()
        return project

    async def delete_project(self, owner_user_id: str, project_id: str) -> bool:
        result = await self._session.execute(
            delete(Project).where(
                Project.id == project_id,
                Project.owner_user_id == owner_user_id,
            )
        )
        return getattr(result, "rowcount", 0) > 0
