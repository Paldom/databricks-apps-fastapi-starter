from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_serving_service
from app.models.integrations.serving_dto import GenericRow
from app.services.integrations.serving_service import ServingService

router = APIRouter(tags=["Integration: Serving"])


@router.post("/serving")
async def serving(
    rows: list[GenericRow],
    service: Annotated[ServingService, Depends(get_serving_service)],
):
    return await service.query(rows)
