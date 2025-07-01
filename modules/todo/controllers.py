from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi_pagination import Page, paginate
from sqlalchemy.ext.asyncio import AsyncSession

from core.sqlalchemy import get_async_session, engine
from .models import Base
from core.deps import get_user_info, get_logger
from logging import Logger
from core.auth import UserInfo
from .repositories import TodoRepository
from .services import TodoService
from .schemas import TodoCreate, TodoRead, TodoUpdate

router = APIRouter(prefix="/todos", tags=["Todo"])


def get_repo(session: Annotated[AsyncSession, Depends(get_async_session)]) -> TodoRepository:
    return TodoRepository(session)


def get_service(
    repo: Annotated[TodoRepository, Depends(get_repo)],
    user: Annotated[UserInfo, Depends(get_user_info)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> TodoService:
    return TodoService(repo, user, logger)




@router.get("/", response_model=Page[TodoRead])
async def list_todos(service: Annotated[TodoService, Depends(get_service)]):
    todos = await service.list()
    return paginate(todos)


@router.post("/", response_model=TodoRead, status_code=status.HTTP_201_CREATED)
async def create_todo(
    payload: TodoCreate,
    service: Annotated[TodoService, Depends(get_service)],
):
    return await service.create(payload)


@router.patch("/{todo_id}", response_model=TodoRead)
async def update_todo(
    todo_id: str,
    payload: TodoUpdate,
    service: Annotated[TodoService, Depends(get_service)],
):
    return await service.update(todo_id, payload)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(
    todo_id: str,
    service: Annotated[TodoService, Depends(get_service)],
):
    await service.delete(todo_id)


@router.get("/{todo_id}", response_model=TodoRead)
async def get_todo(
    todo_id: str,
    service: Annotated[TodoService, Depends(get_service)],
):
    return await service.get(todo_id)


__all__ = ["router", "engine", "Base"]
