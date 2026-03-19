from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.core.config import Settings
from app.core.deps import get_settings
from app.core.health import build_health_report
from app.models.health_dto import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", operation_id="getHealth", response_model=HealthResponse)
async def health(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    report = await build_health_report(request, settings)
    response.status_code = 200 if report.ok else 503
    return report
