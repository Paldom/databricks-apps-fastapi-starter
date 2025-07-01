from fastapi import Request
from databricks.sdk import WorkspaceClient
from workspace import w
from config import settings


async def workspace_client_middleware(request: Request, call_next):
    token = request.headers.get("X-Forwarded-Access-Token")
    if settings.enable_obo and token:
        cfg = w().config
        request.state.w = WorkspaceClient(host=cfg.host, token=token)
    else:
        request.state.w = w()
    response = await call_next(request)
    return response
