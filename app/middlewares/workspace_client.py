from databricks.sdk import WorkspaceClient
from fastapi import Request

from app.core.config import settings
from app.core.databricks.workspace import get_workspace_client_singleton


async def workspace_client_middleware(request: Request, call_next):
    token = request.headers.get("X-Forwarded-Access-Token")
    if settings.enable_obo and token:
        cfg = get_workspace_client_singleton().config
        request.state.w = WorkspaceClient(host=cfg.host, token=token)
    else:
        request.state.w = get_workspace_client_singleton()
    response = await call_next(request)
    return response
