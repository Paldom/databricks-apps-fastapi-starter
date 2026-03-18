from databricks.sdk import WorkspaceClient
from fastapi import Request

from app.core.config import settings
from app.core.integrations import ensure_workspace_client
from app.core.runtime import get_app_runtime


async def workspace_client_middleware(request: Request, call_next):
    runtime = get_app_runtime(request.app)
    request.state.w = None
    token = request.headers.get("X-Forwarded-Access-Token")
    if (
        settings.databricks_integrations_enabled()
        settings.enable_obo
        and token
    ):
        host = settings.databricks_host
        if host is None:
            try:
                host = ensure_workspace_client(runtime, settings).config.host
            except Exception:
                host = None
        if host is not None:
            request.state.w = WorkspaceClient(host=host, token=token)
    response = await call_next(request)
    return response
