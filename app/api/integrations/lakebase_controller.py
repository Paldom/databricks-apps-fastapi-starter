from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_lakebase_service
from app.models.integrations.lakebase_dto import Message
from app.services.integrations.lakebase_demo_service import LakebaseDemoService

router = APIRouter(tags=["Integration: Lakebase"])


@router.post("/pg")
async def pg_demo(
    msg: Message,
    service: Annotated[LakebaseDemoService, Depends(get_lakebase_service)],
):
    return await service.insert(msg.text)
