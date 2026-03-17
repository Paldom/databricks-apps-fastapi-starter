from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.runtime import get_app_runtime

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", operation_id="apiHealthLive")
async def health_live() -> dict:
    return {"status": "alive"}


@router.get("/ready", operation_id="apiHealthReady")
async def health_ready(request: Request) -> dict:
    runtime = get_app_runtime(request.app)
    errors = runtime.init_errors
    if errors:
        return {"status": "degraded", "errors": errors}
    return {"status": "ready"}
