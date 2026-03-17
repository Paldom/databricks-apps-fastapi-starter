from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_user_info, get_vector_search_service
from app.core.security.rate_limit import limiter
from app.models.integrations.vector_search_dto import VectorQueryRequest, VectorStoreRequest
from app.models.user_dto import UserInfo
from app.services.integrations.vector_search_service import VectorSearchService

router = APIRouter(tags=["Integration: Vector Search"])


@router.post("/vector/store")
@limiter.limit("10/minute")
async def vector_store(
    request: Request,
    todo: VectorStoreRequest,
    service: Annotated[VectorSearchService, Depends(get_vector_search_service)],
    user: Annotated[UserInfo, Depends(get_user_info)],
):
    return await service.store(todo.title, user.user_id)


@router.post("/vector/query")
@limiter.limit("20/minute")
async def vector_query(
    request: Request,
    todo: VectorQueryRequest,
    service: Annotated[VectorSearchService, Depends(get_vector_search_service)],
    user: Annotated[UserInfo, Depends(get_user_info)],
):
    return await service.query(todo.title, user.user_id)
