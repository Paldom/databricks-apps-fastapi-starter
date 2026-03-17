"""Centralized rate limiting setup for expensive endpoints."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.observability import increment_counter

logger = logging.getLogger(__name__)


def _rate_limit_key(request: Request) -> str:
    """Derive the rate-limit key from request identity.

    Priority: authenticated user id > email > X-Real-Ip > client host.
    """
    user = getattr(request.state, "user", None)
    if user is not None:
        if user.id:
            return f"user:{user.id}"
        if getattr(user, "email", None):
            return f"email:{user.email}"
    real_ip = request.headers.get("X-Real-Ip")
    if real_ip:
        return f"ip:{real_ip}"
    return f"host:{request.client.host if request.client else 'unknown'}"


limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=[],
    storage_uri="memory://",
    strategy="fixed-window",
    enabled=settings.rate_limit_enabled,
)


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Return a structured 429 response and log the denial."""
    request_id = getattr(request.state, "request_id", None) or "-"
    key = _rate_limit_key(request)

    logger.warning(
        "Rate limit exceeded | route=%s key=%s request_id=%s",
        request.url.path,
        key,
        request_id,
    )
    increment_counter(
        "app.security.rate_limit.denied",
        attributes={"route": request.url.path},
    )

    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded for {request.url.path}",
            "error_code": "rate_limit_exceeded",
            "request_id": request_id,
        },
        headers={"Retry-After": str(exc.detail.split()[-1]) if exc.detail else "60"},
    )
