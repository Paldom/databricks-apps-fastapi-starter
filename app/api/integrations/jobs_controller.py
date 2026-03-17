from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_jobs_service
from app.core.security.rate_limit import limiter
from app.services.integrations.jobs_service import JobsService

router = APIRouter(tags=["Integration: Jobs"])


@router.post("/job")
@limiter.limit("5/minute")
async def run_job(
    request: Request,
    service: Annotated[JobsService, Depends(get_jobs_service)],
    params: Optional[Dict[str, Any]] = None,
):
    return await service.run(params)
