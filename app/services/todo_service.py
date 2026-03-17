from logging import Logger

from app.core.errors import NotFoundError
from app.core.observability import increment_counter, start_span, tag_exception
from app.models.todo_dto import TodoCreate, TodoRead, TodoUpdate, to_dto
from app.models.user_dto import CurrentUser
from app.repositories.todo_repository import TodoRepository

_OP_COUNTER = "app.todo.operation.count"


class TodoService:
    def __init__(self, repo: TodoRepository, user: CurrentUser, logger: Logger):
        self.repo = repo
        self.user = user
        self.logger = logger

    def _uid(self) -> str:
        return self.user.id

    async def list(self) -> list[TodoRead]:
        self.logger.debug("Listing todos")
        with start_span("todo.list") as span:
            try:
                todos = await self.repo.list(created_by=self._uid())
                increment_counter(
                    _OP_COUNTER, attributes={"operation": "list", "result": "ok"}
                )
                return [to_dto(t) for t in todos]
            except Exception as exc:
                tag_exception(span, exc)
                increment_counter(
                    _OP_COUNTER,
                    attributes={"operation": "list", "result": "error"},
                )
                raise

    async def get(self, id_: str) -> TodoRead:
        self.logger.debug("Fetching todo %s", id_)
        with start_span("todo.get", attributes={"todo.id": id_}) as span:
            try:
                todo = await self.repo.get(id_)
                if not todo or todo.created_by != self._uid():
                    raise NotFoundError(f"Todo {id_} not found")
                return to_dto(todo)
            except Exception as exc:
                tag_exception(span, exc)
                raise

    async def create(self, data: TodoCreate) -> TodoRead:
        self.logger.info("Creating todo")
        with start_span("todo.create") as span:
            try:
                todo = await self.repo.create(title=data.title, user=self._uid())
                increment_counter(
                    _OP_COUNTER,
                    attributes={"operation": "create", "result": "ok"},
                )
                return to_dto(todo)
            except Exception as exc:
                tag_exception(span, exc)
                increment_counter(
                    _OP_COUNTER,
                    attributes={"operation": "create", "result": "error"},
                )
                raise

    async def update(self, id_: str, data: TodoUpdate) -> TodoRead:
        self.logger.info("Updating todo %s", id_)
        with start_span("todo.update", attributes={"todo.id": id_}) as span:
            try:
                todo = await self.repo.get(id_)
                if not todo or todo.created_by != self._uid():
                    raise NotFoundError(f"Todo {id_} not found")
                if data.title is not None:
                    todo.title = data.title
                if data.completed is not None:
                    todo.completed = data.completed
                todo.updated_by = self._uid()
                todo = await self.repo.update(todo)
                increment_counter(
                    _OP_COUNTER,
                    attributes={"operation": "update", "result": "ok"},
                )
                return to_dto(todo)
            except Exception as exc:
                tag_exception(span, exc)
                increment_counter(
                    _OP_COUNTER,
                    attributes={"operation": "update", "result": "error"},
                )
                raise

    async def delete(self, id_: str) -> None:
        self.logger.info("Deleting todo %s", id_)
        with start_span("todo.delete", attributes={"todo.id": id_}) as span:
            try:
                todo = await self.repo.get(id_)
                if not todo or todo.created_by != self._uid():
                    raise NotFoundError(f"Todo {id_} not found")
                await self.repo.delete(todo)
                increment_counter(
                    _OP_COUNTER,
                    attributes={"operation": "delete", "result": "ok"},
                )
            except Exception as exc:
                tag_exception(span, exc)
                increment_counter(
                    _OP_COUNTER,
                    attributes={"operation": "delete", "result": "error"},
                )
                raise
