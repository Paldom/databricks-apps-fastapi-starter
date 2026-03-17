from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_ai_gateway_service
from app.models.todo_dto import TodoCreate
from app.services.integrations.ai_gateway_service import AiGatewayService

router = APIRouter(tags=["Integration: AI Gateway"])


@router.post("/embed")
async def embed(
    todo: TodoCreate,
    service: Annotated[AiGatewayService, Depends(get_ai_gateway_service)],
):
    vector = await service.embed(todo.title)
    return {"vector": vector}
