from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi_pagination import add_pagination
from slowapi.errors import RateLimitExceeded

from app.api.api import api_router
from app.api.health_controller import router as health_router
from app.core.bootstrap import lifespan
from app.core.config import settings
from app.core.errors import AppError
from app.core.security.rate_limit import limiter, rate_limit_exceeded_handler
from app.middlewares.request_context import request_context_middleware
from app.middlewares.request_size import RequestSizeMiddleware
from app.middlewares.security_headers import security_headers_middleware
from app.middlewares.user_info import user_info_middleware
from app.middlewares.workspace_client import workspace_client_middleware


def create_app() -> FastAPI:
    kwargs: dict = {"lifespan": lifespan}
    if settings.environment == "production":
        kwargs.update(docs_url=None, openapi_url=None, redoc_url=None)

    application = FastAPI(**kwargs)

    # Rate limiter state
    application.state.limiter = limiter

    # Global exception handlers
    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    application.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Middleware (order matters: last added = first executed)
    application.middleware("http")(user_info_middleware)
    application.middleware("http")(workspace_client_middleware)
    application.middleware("http")(security_headers_middleware)
    application.middleware("http")(request_context_middleware)

    # Pure ASGI middleware — outermost, runs before all http middleware
    application.add_middleware(
        RequestSizeMiddleware,
        max_bytes=settings.max_request_body_bytes,
        max_upload_bytes=settings.max_upload_bytes,
    )

    # Routes
    application.include_router(health_router)
    application.include_router(api_router, prefix="/api/v1")
    application.include_router(api_router, prefix="/v1", include_in_schema=False)

    add_pagination(application)
    return application


app = create_app()
