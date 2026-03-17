from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_ai_gateway_service
from app.core.security.rate_limit import limiter
from app.models.todo_dto import TodoCreate
from app.services.integrations.ai_gateway_service import AiGatewayService

router = APIRouter(tags=["Integration: AI Gateway"])


@router.post("/embed")
@limiter.limit("20/minute")
async def embed(
    request: Request,
    todo: TodoCreate,
    service: Annotated[AiGatewayService, Depends(get_ai_gateway_service)],
):
    vector = await service.embed(todo.title)
    return {"vector": vector}
