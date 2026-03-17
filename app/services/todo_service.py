from logging import Logger

from app.core.errors import NotFoundError
from app.core.observability import increment_counter, start_span, tag_exception
from app.models.todo_dto import TodoCreate, TodoRead, TodoUpdate, to_dto
from app.models.user_dto import CurrentUser
from app.repositories.todo_command_repository import TodoCommandRepository
from app.repositories.todo_query_repository import TodoQueryRepository

_OP_COUNTER = "app.todo.operation.count"


class TodoService:
    def __init__(
        self,
        query_repo: TodoQueryRepository,
        command_repo: TodoCommandRepository,
        user: CurrentUser,
        logger: Logger,
    ):
        self.query_repo = query_repo
        self.command_repo = command_repo
        self.user = user
        self.logger = logger

    async def list(self) -> list[TodoRead]:
        self.logger.debug("Listing todos")
        with start_span("todo.list") as span:
            try:
                todos = await self.query_repo.list()
                increment_counter(
                    _OP_COUNTER, attributes={"operation": "list", "result": "ok"}
                )
                return todos
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
                dto = await self.query_repo.get(id_)
                if dto is None:
                    raise NotFoundError(f"Todo {id_} not found")
                return dto
            except Exception as exc:
                tag_exception(span, exc)
                raise

    async def create(self, data: TodoCreate) -> TodoRead:
        self.logger.info("Creating todo")
        with start_span("todo.create") as span:
            try:
                todo = await self.command_repo.create(title=data.title)
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
                todo = await self.command_repo.get_for_update(id_)
                if not todo:
                    raise NotFoundError(f"Todo {id_} not found")
                if data.title is not None:
                    todo.title = data.title
                if data.completed is not None:
                    todo.completed = data.completed
                todo.updated_by = self.user.id
                todo = await self.command_repo.update(todo)
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
                todo = await self.command_repo.get_for_update(id_)
                if not todo:
                    raise NotFoundError(f"Todo {id_} not found")
                await self.command_repo.delete(todo)
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
