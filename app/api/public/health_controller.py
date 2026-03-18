from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.core.config import Settings
from app.core.deps import get_settings
from app.core.health import (
    build_integrations_report,
    build_live_report,
    build_ready_report,
)
from app.models.health_dto import (
    IntegrationsHealthResponse,
    LiveHealthResponse,
    ReadyHealthResponse,
)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", operation_id="apiHealthLive", response_model=LiveHealthResponse)
async def health_live() -> LiveHealthResponse:
    return build_live_report()


@router.get(
    "/ready",
    operation_id="apiHealthReady",
    response_model=ReadyHealthResponse,
)
async def health_ready(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadyHealthResponse:
    report = await build_ready_report(request, settings)
    response.status_code = 200 if report.ok else 503
    return report


@router.get(
    "/integrations",
    operation_id="apiHealthIntegrations",
    response_model=IntegrationsHealthResponse,
)
async def health_integrations(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> IntegrationsHealthResponse:
    report = build_integrations_report(request, settings)
    response.status_code = 200 if report.ok else 503
    return report
