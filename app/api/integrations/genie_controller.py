from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_genie_service
from app.services.integrations.genie_service import GenieService

router = APIRouter(tags=["Integration: Genie"])


@router.post("/genie/{space_id}/ask")
async def genie_start_conversation(
    space_id: str,
    question: str,
    service: Annotated[GenieService, Depends(get_genie_service)],
):
    return await service.start_conversation(space_id, question)


@router.post("/genie/{space_id}/{conversation_id}/ask")
async def genie_follow_up(
    space_id: str,
    conversation_id: str,
    question: str,
    service: Annotated[GenieService, Depends(get_genie_service)],
):
    return await service.follow_up(space_id, conversation_id, question)
