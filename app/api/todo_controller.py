from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi_pagination import Page, paginate

from app.core.deps import get_todo_service
from app.core.http_cache import build_etag, if_none_match_matches
from app.models.todo_dto import TodoCreate, TodoRead, TodoUpdate
from app.services.todo_service import TodoService

router = APIRouter(prefix="/todos", tags=["Todo"])

_CACHE_CONTROL = "private, no-cache"


@router.get("/", response_model=Page[TodoRead])
async def list_todos(
    request: Request,
    response: Response,
    service: Annotated[TodoService, Depends(get_todo_service)],
):
    todos = await service.list()
    page = paginate(todos)

    etag = build_etag(page.model_dump(mode="json"))
    if if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={"ETag": etag, "Cache-Control": _CACHE_CONTROL},
        )

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = _CACHE_CONTROL
    return page


@router.post("/", response_model=TodoRead, status_code=status.HTTP_201_CREATED)
async def create_todo(
    payload: TodoCreate,
    service: Annotated[TodoService, Depends(get_todo_service)],
):
    return await service.create(payload)


@router.patch("/{todo_id}", response_model=TodoRead)
async def update_todo(
    todo_id: str,
    payload: TodoUpdate,
    service: Annotated[TodoService, Depends(get_todo_service)],
):
    return await service.update(todo_id, payload)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(
    todo_id: str,
    service: Annotated[TodoService, Depends(get_todo_service)],
):
    await service.delete(todo_id)


@router.get("/{todo_id}", response_model=TodoRead)
async def get_todo(
    todo_id: str,
    request: Request,
    response: Response,
    service: Annotated[TodoService, Depends(get_todo_service)],
):
    todo = await service.get(todo_id)

    etag = build_etag(todo.model_dump(mode="json"))
    if if_none_match_matches(request.headers.get("if-none-match"), etag):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={"ETag": etag, "Cache-Control": _CACHE_CONTROL},
        )

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = _CACHE_CONTROL
    return todo
