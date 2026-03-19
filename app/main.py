from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import build_api_router
from app.core.bootstrap import lifespan
from app.core.config import Settings, settings
from app.core.errors import AppError
from app.middlewares.request_context import request_context_middleware
from app.middlewares.request_size import RequestSizeMiddleware
from app.middlewares.security_headers import security_headers_middleware
from app.middlewares.user_info import user_info_middleware
from app.middlewares.workspace_client import workspace_client_middleware


def _app_error_response(exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


def no_cache(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _patch_openapi_schema(schema: dict) -> None:
    """Patch the auto-generated OpenAPI schema for frontend compatibility."""
    from app.api.chat_stream_controller import STREAMING_EVENT_MODELS

    schemas = schema.setdefault("components", {}).setdefault("schemas", {})

    # ── Inject streaming event schemas ─────────────────────────────
    for model in STREAMING_EVENT_MODELS:
        name = model.__name__
        model_schema = model.model_json_schema()
        model_schema.pop("$defs", None)
        schemas[name] = model_schema

    schemas["ChatStreamEvent"] = {
        "oneOf": [
            {"$ref": f"#/components/schemas/{m.__name__}"}
            for m in STREAMING_EVENT_MODELS
        ],
        "discriminator": {
            "propertyName": "type",
            "mapping": {
                "text-delta": "#/components/schemas/TextDeltaEvent",
                "tool-call-begin": "#/components/schemas/ToolCallBeginEvent",
                "tool-call-delta": "#/components/schemas/ToolCallDeltaEvent",
                "done": "#/components/schemas/DoneEvent",
                "error": "#/components/schemas/ErrorEvent",
            },
        },
    }

    # Update /chat/stream response to reference ChatStreamEvent
    chat_stream = schema.get("paths", {}).get("/chat/stream", {}).get("post", {})
    resp_200 = chat_stream.get("responses", {}).get("200", {})
    content = resp_200.get("content", {})
    content.pop("application/json", None)
    content["application/x-ndjson"] = {
        "schema": {"$ref": "#/components/schemas/ChatStreamEvent"},
    }

    # ── Strip 422 validation error responses ───────────────────────
    # FastAPI auto-adds these; they pollute Orval's generated return types
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                operation.get("responses", {}).pop("422", None)

    # Remove unused HTTPValidationError / ValidationError schemas
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)

    # ── Fix upload file field to use format: binary ────────────────
    upload_body = schemas.get("Body_uploadDocument", {})
    file_prop = upload_body.get("properties", {}).get("file", {})
    if file_prop:
        file_prop.pop("contentMediaType", None)
        file_prop["format"] = "binary"


def build_api_app(s: Settings) -> FastAPI:
    """Build the API sub-app (mounted at /api) with all frontend-facing routes."""
    api_app = FastAPI(
        title="Databricks Apps FastAPI Starter API",
        version="0.1.0",
        openapi_url="/openapi.json",
        docs_url="/docs" if s.enable_docs else None,
        redoc_url="/redoc" if s.enable_docs else None,
    )

    @api_app.exception_handler(AppError)
    async def api_app_error_handler(request: Request, exc: AppError):
        return _app_error_response(exc)

    api_app.include_router(build_api_router())

    # Custom OpenAPI hook to inject streaming event schemas
    _default_openapi = api_app.openapi

    def custom_openapi():
        if api_app.openapi_schema:
            return api_app.openapi_schema
        schema = _default_openapi()
        _patch_openapi_schema(schema)
        api_app.openapi_schema = schema
        return schema

    api_app.openapi = custom_openapi  # type: ignore[method-assign]

    return api_app


def build_root_app(s: Settings) -> FastAPI:
    """Build the root app with lifespan, middleware, API mount, and optional SPA serving."""
    application = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return _app_error_response(exc)

    # Middleware (order matters: last added = first executed)
    application.middleware("http")(user_info_middleware)
    application.middleware("http")(workspace_client_middleware)
    application.middleware("http")(security_headers_middleware)
    application.middleware("http")(request_context_middleware)

    if s.environment == "development":
        application.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Pure ASGI middleware — outermost, runs before all http middleware
    application.add_middleware(
        RequestSizeMiddleware,
        max_bytes=s.max_request_body_bytes,
        max_upload_bytes=s.max_upload_bytes,
    )

    api_app = build_api_app(s)
    api_app.dependency_overrides_provider = application
    application.mount("/api", api_app)

    if s.serve_static:
        static_dir = Path(s.frontend_dist_dir).resolve()
        index_file = static_dir / "index.html"

        @application.exception_handler(StarletteHTTPException)
        async def spa_404_handler(
            request: Request,
            exc: StarletteHTTPException,
        ) -> Response:
            if (
                exc.status_code == 404
                and not request.url.path.startswith("/api")
                and index_file.exists()
            ):
                return no_cache(FileResponse(index_file))
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

        @application.get("/{full_path:path}", include_in_schema=False)
        async def serve_frontend(full_path: str) -> Response:
            if not static_dir.exists():
                raise HTTPException(status_code=404, detail="Frontend dist not built")

            candidate = (static_dir / full_path).resolve()
            try:
                candidate.relative_to(static_dir)
            except ValueError as exc:
                raise HTTPException(status_code=404) from exc

            if candidate.is_file():
                if candidate.name == "index.html":
                    return no_cache(FileResponse(candidate))
                return FileResponse(
                    candidate,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"},
                )

            raise HTTPException(status_code=404, detail="Not Found")

    return application


def create_app() -> FastAPI:
    return build_root_app(settings)


app = create_app()
