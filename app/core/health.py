from __future__ import annotations

from fastapi import Request
from sqlalchemy import text

from app.core.config import Settings
from app.core.errors import ConfigurationError, ServiceUnavailableError
from app.core.integrations import (
    ai_not_configured_message,
    databricks_integrations_disabled_message,
    ensure_ai_client,
    ensure_vector_index,
    ensure_workspace_client,
    vector_not_configured_message,
)
from app.core.runtime import AppRuntime, get_app_runtime
from app.models.health_dto import (
    DependencyHealth,
    DependencyHealthStatus,
    HealthResponseStatus,
    IntegrationsHealthResponse,
    LiveHealthResponse,
    ReadyHealthResponse,
)
from app.core.db.url import DATABASE_NOT_CONFIGURED_MESSAGE


def _dependency(
    status: DependencyHealthStatus,
    *,
    required: bool = False,
    disabled: bool = False,
    reason: str | None = None,
) -> DependencyHealth:
    return DependencyHealth(
        status=status,
        required=required,
        disabled=disabled,
        reason=reason,
    )


async def _database_dependency(
    runtime: AppRuntime,
    settings: Settings,
) -> DependencyHealth:
    if not settings.has_database_config():
        runtime.not_configured("database", DATABASE_NOT_CONFIGURED_MESSAGE)
        return _dependency(
            DependencyHealthStatus.NOT_CONFIGURED,
            required=True,
            reason=DATABASE_NOT_CONFIGURED_MESSAGE,
        )

    if runtime.engine is None:
        detail = runtime.error_for("database") or "Database engine is unavailable"
        return _dependency(
            DependencyHealthStatus.FAIL,
            required=True,
            reason=detail,
        )

    try:
        async with runtime.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        runtime.clear_error("database")
        return _dependency(
            DependencyHealthStatus.OK,
            required=True,
            reason="SELECT 1 succeeded",
        )
    except Exception as exc:
        runtime.remember_error("database", exc)
        return _dependency(
            DependencyHealthStatus.FAIL,
            required=True,
            reason=str(exc) or exc.__class__.__name__,
        )


def _disabled_dependency() -> DependencyHealth:
    return _dependency(
        DependencyHealthStatus.DISABLED,
        disabled=True,
        reason=databricks_integrations_disabled_message(),
    )


def _workspace_dependency(runtime: AppRuntime, settings: Settings) -> DependencyHealth:
    if not settings.databricks_integrations_enabled():
        return _disabled_dependency()

    try:
        ensure_workspace_client(runtime, settings)
        return _dependency(
            DependencyHealthStatus.OK,
            reason="Workspace client initialized",
        )
    except ConfigurationError as exc:
        return _dependency(
            DependencyHealthStatus.NOT_CONFIGURED,
            reason=exc.detail,
        )
    except ServiceUnavailableError as exc:
        return _dependency(
            DependencyHealthStatus.FAIL,
            reason=exc.detail,
        )


def _ai_dependency(runtime: AppRuntime, settings: Settings) -> DependencyHealth:
    if not settings.databricks_integrations_enabled():
        return _disabled_dependency()

    if not settings.has_ai_config():
        return _dependency(
            DependencyHealthStatus.NOT_CONFIGURED,
            reason=ai_not_configured_message(),
        )

    try:
        ensure_ai_client(runtime, settings)
        return _dependency(
            DependencyHealthStatus.OK,
            reason="AI client initialized",
        )
    except ConfigurationError as exc:
        return _dependency(
            DependencyHealthStatus.NOT_CONFIGURED,
            reason=exc.detail,
        )
    except ServiceUnavailableError as exc:
        return _dependency(
            DependencyHealthStatus.FAIL,
            reason=exc.detail,
        )


def _vector_dependency(runtime: AppRuntime, settings: Settings) -> DependencyHealth:
    if not settings.databricks_integrations_enabled():
        return _disabled_dependency()

    if not settings.has_vector_search_config():
        return _dependency(
            DependencyHealthStatus.NOT_CONFIGURED,
            reason=vector_not_configured_message(),
        )

    try:
        ensure_vector_index(runtime, settings)
        return _dependency(
            DependencyHealthStatus.OK,
            reason="Vector Search index initialized",
        )
    except ConfigurationError as exc:
        return _dependency(
            DependencyHealthStatus.NOT_CONFIGURED,
            reason=exc.detail,
        )
    except ServiceUnavailableError as exc:
        return _dependency(
            DependencyHealthStatus.FAIL,
            reason=exc.detail,
        )


def build_live_report() -> LiveHealthResponse:
    return LiveHealthResponse(status=HealthResponseStatus.ALIVE)


async def build_ready_report(
    request: Request,
    settings: Settings,
) -> ReadyHealthResponse:
    runtime = get_app_runtime(request.app)
    db = await _database_dependency(runtime, settings)
    ok = db.status == DependencyHealthStatus.OK
    status = HealthResponseStatus.READY if ok else HealthResponseStatus.NOT_READY
    return ReadyHealthResponse(ok=ok, status=status, db=db)


def build_integrations_report(
    request: Request,
    settings: Settings,
) -> IntegrationsHealthResponse:
    runtime = get_app_runtime(request.app)
    workspace = _workspace_dependency(runtime, settings)
    ai = _ai_dependency(runtime, settings)
    vector_search = _vector_dependency(runtime, settings)

    statuses = [workspace.status, ai.status, vector_search.status]
    ok = DependencyHealthStatus.FAIL not in statuses
    status = (
        HealthResponseStatus.READY
        if all(item == DependencyHealthStatus.OK for item in statuses)
        else HealthResponseStatus.DEGRADED
    )
    return IntegrationsHealthResponse(
        ok=ok,
        status=status,
        workspace=workspace,
        ai=ai,
        vector_search=vector_search,
    )
