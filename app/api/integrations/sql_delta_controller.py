from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_sql_delta_service
from app.models.todo_dto import TodoCreate, TodoRead
from app.services.integrations.sql_delta_service import SqlDeltaService

router = APIRouter(tags=["Integration: Delta SQL"])


@router.get("/delta/todos", response_model=list[TodoRead])
def list_delta_todos(
    service: Annotated[SqlDeltaService, Depends(get_sql_delta_service)],
    limit: int = 100,
):
    return service.list_todos(limit)


@router.post("/delta/todos", status_code=201)
def add_delta_todo(
    todo: TodoCreate,
    service: Annotated[SqlDeltaService, Depends(get_sql_delta_service)],
):
    return service.insert_todo(todo.title)
