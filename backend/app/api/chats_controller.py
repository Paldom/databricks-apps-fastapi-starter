from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import ConfigDict

from app.api.common.schemas import ApiModel, CursorPage
from app.core.deps import get_chat_service
from app.services.chat_service import ChatService

router = APIRouter(tags=["chats"])


class Chat(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "c4",
                "title": "Q1 metrics summary",
                "projectId": "work",
                "createdAt": "2024-01-15T10:00:00Z",
                "updatedAt": "2024-01-15T10:00:00Z",
            }
        }
    )

    id: str
    title: str
    project_id: str
    created_at: datetime
    updated_at: datetime


class ChatSearchResult(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "c4",
                "title": "Q1 metrics summary",
                "projectId": "work",
                "projectName": "Work",
                "createdAt": "2024-01-15T10:00:00Z",
                "updatedAt": "2024-01-15T10:00:00Z",
            }
        }
    )

    id: str
    title: str
    project_id: str
    project_name: str
    created_at: datetime
    updated_at: datetime


class PaginatedChats(CursorPage[Chat]):
    pass


class PaginatedChatSearchResults(CursorPage[ChatSearchResult]):
    pass


class CreateChatRequest(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"title": "New chat"}}
    )

    title: str


class UpdateChatRequest(ApiModel):
    title: str | None = None


def _to_chat(d: dict) -> Chat:
    return Chat(
        id=d["id"],
        title=d["title"],
        project_id=d["project_id"],
        created_at=d["created_at"],
        updated_at=d["updated_at"],
    )


def _to_search_result(d: dict) -> ChatSearchResult:
    return ChatSearchResult(
        id=d["id"],
        title=d["title"],
        project_id=d["project_id"],
        project_name=d["project_name"],
        created_at=d["created_at"],
        updated_at=d["updated_at"],
    )


@router.get(
    "/projects/{projectId}/chats",
    operation_id="listProjectChats",
    response_model=PaginatedChats,
)
async def list_project_chats(
    projectId: str,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    service: ChatService = Depends(get_chat_service),
) -> PaginatedChats:
    result = await service.list_project_chats(
        project_id=projectId, cursor=cursor, limit=limit,
    )
    return PaginatedChats(
        items=[_to_chat(i) for i in result["items"]],
        next_cursor=result["next_cursor"],
        has_more=result["has_more"],
    )


@router.post(
    "/projects/{projectId}/chats",
    operation_id="createProjectChat",
    response_model=Chat,
    status_code=201,
)
async def create_project_chat(
    projectId: str,
    body: CreateChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> Chat:
    result = await service.create_chat(project_id=projectId, title=body.title)
    return _to_chat(result)


@router.patch(
    "/chats/{chatId}",
    operation_id="updateChat",
    response_model=Chat,
)
async def update_chat(
    chatId: str,
    body: UpdateChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> Chat:
    result = await service.update_chat(chat_id=chatId, title=body.title)
    if result is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return _to_chat(result)


@router.delete(
    "/chats/{chatId}",
    operation_id="deleteChat",
    status_code=204,
)
async def delete_chat(
    chatId: str,
    service: ChatService = Depends(get_chat_service),
) -> Response:
    deleted = await service.delete_chat(chat_id=chatId)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat not found")
    return Response(status_code=204)


@router.get(
    "/chats/search",
    operation_id="searchChats",
    response_model=PaginatedChatSearchResults,
)
async def search_chats(
    q: str = Query(min_length=1),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    service: ChatService = Depends(get_chat_service),
) -> PaginatedChatSearchResults:
    result = await service.search_chats(q=q, cursor=cursor, limit=limit)
    return PaginatedChatSearchResults(
        items=[_to_search_result(i) for i in result["items"]],
        next_cursor=result["next_cursor"],
        has_more=result["has_more"],
    )


@router.get(
    "/chats/recent",
    operation_id="getRecentChats",
    response_model=PaginatedChatSearchResults,
)
async def get_recent_chats(
    limit: int = Query(default=10, ge=1, le=50),
    service: ChatService = Depends(get_chat_service),
) -> PaginatedChatSearchResults:
    result = await service.get_recent_chats(limit=limit)
    return PaginatedChatSearchResults(
        items=[_to_search_result(i) for i in result["items"]],
        next_cursor=result["next_cursor"],
        has_more=result["has_more"],
    )
