from __future__ import annotations

from app.repositories.project_repository import ProjectRepository


class ProjectService:
    def __init__(self, repo: ProjectRepository, user_id: str) -> None:
        self._repo = repo
        self._user_id = user_id

    async def list_projects(self, cursor: str | None, limit: int) -> dict:
        items, next_cursor, has_more = await self._repo.list_projects(
            self._user_id, cursor, limit,
        )
        return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

    async def create_project(self, name: str) -> dict:
        project = await self._repo.create_project(self._user_id, name)
        return {
            "id": project.id,
            "name": project.name,
            "created_at": project.created_at,
            "chat_count": 0,
        }

    async def update_project(self, project_id: str, name: str) -> dict | None:
        project = await self._repo.update_project(self._user_id, project_id, name)
        if project is None:
            return None
        return {
            "id": project.id,
            "name": project.name,
            "created_at": project.created_at,
            "chat_count": 0,  # Simplified; could count
        }

    async def delete_project(self, project_id: str) -> bool:
        return await self._repo.delete_project(self._user_id, project_id)
