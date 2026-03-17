from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_genie_service
from app.core.security.rate_limit import limiter
from app.models.integrations.genie_dto import GenieQuestion
from app.services.integrations.genie_service import GenieService

router = APIRouter(tags=["Integration: Genie"])


@router.post("/genie/{space_id}/ask")
@limiter.limit("5/minute")
async def genie_start_conversation(
    request: Request,
    space_id: str,
    body: GenieQuestion,
    service: Annotated[GenieService, Depends(get_genie_service)],
):
    return await service.start_conversation(space_id, body.content)


@router.post("/genie/{space_id}/{conversation_id}/ask")
@limiter.limit("20/minute")
async def genie_follow_up(
    request: Request,
    space_id: str,
    conversation_id: str,
    body: GenieQuestion,
    service: Annotated[GenieService, Depends(get_genie_service)],
):
    return await service.follow_up(space_id, conversation_id, body.content)
