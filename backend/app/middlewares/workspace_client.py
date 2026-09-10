from databricks.sdk import WorkspaceClient
from fastapi import Request

from app.core.config import settings
from app.core.context import obo_workspace_client
from app.core.integrations import ensure_workspace_client
from app.core.runtime import get_app_runtime


async def workspace_client_middleware(request: Request, call_next):
    """Build a per-request, user-scoped ``WorkspaceClient`` when OBO is on.

    The forwarded access token is only honoured when the identity headers are
    trusted (running inside Databricks Apps, or a non-production environment).
    The client is exposed as ``request.state.w`` and through the
    ``obo_workspace_client`` context variable; the token itself is never stored
    on the request or logged.
    """
    runtime = get_app_runtime(request.app)
    request.state.w = None
    token = request.headers.get("X-Forwarded-Access-Token")
    if (
        settings.databricks_integrations_enabled()
        and settings.enable_obo
        and settings.trust_forwarded_identity()
        and token
    ):
        host = settings.databricks_host
        if host is None:
            try:
                host = ensure_workspace_client(runtime, settings).config.host
            except Exception:
                host = None
        if host is not None:
            # auth_type pins the forwarded token; otherwise the SDK may pick the
            # app's own OAuth env credentials or reject the mix as ambiguous.
            request.state.w = WorkspaceClient(host=host, token=token, auth_type="pat")
    ctx_token = obo_workspace_client.set(request.state.w)
    try:
        return await call_next(request)
    finally:
        obo_workspace_client.reset(ctx_token)
