from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends

from app.core.deps import get_jobs_service
from app.services.integrations.jobs_service import JobsService

router = APIRouter(tags=["Integration: Jobs"])


@router.post("/job")
async def run_job(
    service: Annotated[JobsService, Depends(get_jobs_service)],
    params: Optional[Dict[str, Any]] = None,
):
    return await service.run(params)
