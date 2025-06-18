from fastapi import status

from core.errors import http_error

from core.auth import UserInfo
from logging import Logger

from .repositories import TodoRepository
from .schemas import TodoCreate, TodoRead, TodoUpdate
from .mappers import to_dto


class TodoService:
    def __init__(self, repo: TodoRepository, user: UserInfo, logger: Logger):
        self.repo = repo
        self.user = user
        self.logger = logger

    def _uid(self) -> str:
        """Return the authenticated user identifier or raise."""
        if self.user.user_id:
            return self.user.user_id
        raise http_error(status.HTTP_401_UNAUTHORIZED, "User ID missing")

    async def list(self) -> list[TodoRead]:
        self.logger.debug("Listing todos for user %s", self._uid())
        todos = await self.repo.list(created_by=self._uid())
        return [to_dto(t) for t in todos]

    async def get(self, id_: str) -> TodoRead:
        self.logger.debug("Fetching todo %s", id_)
        todo = await self.repo.get(id_)
        if not todo or todo.created_by != self._uid():
            raise http_error(status.HTTP_404_NOT_FOUND, f"Todo {id_} not found")
        return to_dto(todo)

    async def create(self, data: TodoCreate) -> TodoRead:
        self.logger.info("Creating todo for user %s", self._uid())
        todo = await self.repo.create(title=data.title, user=self._uid())
        return to_dto(todo)

    async def update(self, id_: str, data: TodoUpdate) -> TodoRead:
        self.logger.info("Updating todo %s", id_)
        todo = await self.repo.get(id_)
        if not todo or todo.created_by != self._uid():
            raise http_error(status.HTTP_404_NOT_FOUND, f"Todo {id_} not found")
        if data.title is not None:
            todo.title = data.title
        if data.completed is not None:
            todo.completed = data.completed
        todo.updated_by = self._uid()
        todo = await self.repo.update(todo)
        return to_dto(todo)

    async def delete(self, id_: str) -> None:
        self.logger.info("Deleting todo %s", id_)
        todo = await self.repo.get(id_)
        if not todo or todo.created_by != self._uid():
            raise http_error(status.HTTP_404_NOT_FOUND, f"Todo {id_} not found")
        await self.repo.delete(todo)
