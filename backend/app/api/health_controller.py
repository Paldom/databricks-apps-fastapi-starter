from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.core.config import Settings
from app.core.deps import get_settings
from app.core.health import build_detailed_health, check_database
from app.core.runtime import get_app_runtime
from app.models.health_dto import (
    DetailedHealthResponse,
    HealthStatus,
    LiveResponse,
    ReadyResponse,
)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", operation_id="healthLive", response_model=LiveResponse)
async def live() -> LiveResponse:
    return LiveResponse()


@router.get("/ready", operation_id="healthReady", response_model=ReadyResponse)
async def ready(request: Request, response: Response) -> ReadyResponse:
    runtime = get_app_runtime(request.app)
    db = await check_database(runtime)
    db_ok = db.status == HealthStatus.OK
    result = ReadyResponse(ok=db_ok, db=db_ok)
    if not result.ok:
        response.status_code = 503
    return result


@router.get("", operation_id="getHealth", response_model=DetailedHealthResponse)
async def health(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DetailedHealthResponse:
    runtime = get_app_runtime(request.app)
    report = await build_detailed_health(runtime, settings)
    if not report.ok:
        response.status_code = 503
    return report
