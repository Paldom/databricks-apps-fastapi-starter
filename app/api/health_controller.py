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

router = APIRouter(tags=["Health"])


@router.get("/healthcheck", response_model=LiveHealthResponse)
@router.get("/health/live", response_model=LiveHealthResponse, include_in_schema=False)
async def live() -> LiveHealthResponse:
    return build_live_report()


@router.get("/databasehealthcheck", response_model=ReadyHealthResponse)
@router.get("/health/ready", response_model=ReadyHealthResponse)
async def ready(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadyHealthResponse:
    report = await build_ready_report(request, settings)
    response.status_code = 200 if report.ok else 503
    return report


@router.get("/health/integrations", response_model=IntegrationsHealthResponse)
@router.get("/health/deep", response_model=IntegrationsHealthResponse)
async def integrations(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> IntegrationsHealthResponse:
    report = build_integrations_report(request, settings)
    response.status_code = 200 if report.ok else 503
    return report
