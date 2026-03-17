"""Request context middleware -- request-id propagation and safe span attributes."""

import uuid
from contextvars import ContextVar

from fastapi import Request
from opentelemetry import trace

from app.core.config import settings

REQUEST_ID_HEADER = "X-Request-ID"

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Read the current request_id from context. Used by the logging filter."""
    return _request_id_var.get()


async def request_context_middleware(request: Request, call_next):
    """Establish request-scoped context: request_id, safe span attrs."""
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
    _request_id_var.set(request_id)
    request.state.request_id = request_id

    response = await call_next(request)

    # Set safe span attributes after downstream middleware has populated
    # request.state (user_info, workspace_client).
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute("app.request_id", request_id)
        span.set_attribute(
            "app.user.present",
            getattr(request.state, "user", None) is not None,
        )
        span.set_attribute(
            "app.auth.obo",
            settings.enable_obo
            and bool(request.headers.get("X-Forwarded-Access-Token")),
        )

    response.headers[REQUEST_ID_HEADER] = request_id
    return response
