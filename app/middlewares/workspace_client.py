from databricks.sdk import WorkspaceClient
from fastapi import Request

from app.core.config import settings
from app.core.runtime import get_app_runtime


async def workspace_client_middleware(request: Request, call_next):
    runtime = get_app_runtime(request.app)
    token = request.headers.get("X-Forwarded-Access-Token")
    if (
        settings.enable_obo
        and token
        and runtime.workspace_client is not None
    ):
        cfg = runtime.workspace_client.config
        request.state.w = WorkspaceClient(host=cfg.host, token=token)
    else:
        request.state.w = runtime.workspace_client
    response = await call_next(request)
    return response
