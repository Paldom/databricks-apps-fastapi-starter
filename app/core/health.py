from __future__ import annotations

from fastapi import Request
from sqlalchemy import text

from app.core.config import Settings
from app.core.db.url import DATABASE_NOT_CONFIGURED_MESSAGE
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
    HealthChecks,
    HealthResponse,
    HealthResponseStatus,
)


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


def _configured_dependency(
    workspace: DependencyHealth,
    *,
    configured: bool,
    missing_reason: str,
    ready_reason: str,
) -> DependencyHealth:
    if workspace.status == DependencyHealthStatus.DISABLED:
        return _disabled_dependency()
    if not configured:
        return _dependency(
            DependencyHealthStatus.NOT_CONFIGURED,
            reason=missing_reason,
        )
    if workspace.status == DependencyHealthStatus.FAIL:
        return _dependency(
            DependencyHealthStatus.FAIL,
            reason=workspace.reason,
        )
    if workspace.status == DependencyHealthStatus.NOT_CONFIGURED:
        return _dependency(
            DependencyHealthStatus.NOT_CONFIGURED,
            reason=workspace.reason,
        )
    return _dependency(
        DependencyHealthStatus.OK,
        reason=ready_reason,
    )


def _jobs_dependency(
    workspace: DependencyHealth,
    settings: Settings,
) -> DependencyHealth:
    return _configured_dependency(
        workspace,
        configured=bool(settings.job_id),
        missing_reason="JOB_ID not configured",
        ready_reason="Job ID configured",
    )


def _knowledge_assistant_dependency(
    workspace: DependencyHealth,
    settings: Settings,
) -> DependencyHealth:
    return _configured_dependency(
        workspace,
        configured=settings.has_knowledge_assistant_config(),
        missing_reason="KNOWLEDGE_ASSISTANT_ENDPOINT not configured",
        ready_reason="Knowledge Assistant endpoint configured",
    )


async def build_health_report(
    request: Request,
    settings: Settings,
) -> HealthResponse:
    runtime = get_app_runtime(request.app)
    database = await _database_dependency(runtime, settings)
    workspace = _workspace_dependency(runtime, settings)
    ai = _ai_dependency(runtime, settings)
    vector_search = _vector_dependency(runtime, settings)
    jobs = _jobs_dependency(workspace, settings)
    knowledge_assistant = _knowledge_assistant_dependency(workspace, settings)

    optional_checks = [workspace, ai, vector_search, jobs, knowledge_assistant]
    has_failures = database.status != DependencyHealthStatus.OK or any(
        check.status == DependencyHealthStatus.FAIL for check in optional_checks
    )
    has_degraded = any(
        check.status
        in {
            DependencyHealthStatus.DISABLED,
            DependencyHealthStatus.NOT_CONFIGURED,
        }
        for check in optional_checks
    )

    if has_failures:
        ok = False
        status = HealthResponseStatus.FAIL
    elif has_degraded:
        ok = True
        status = HealthResponseStatus.DEGRADED
    else:
        ok = True
        status = HealthResponseStatus.OK

    return HealthResponse(
        ok=ok,
        status=status,
        checks=HealthChecks(
            database=database,
            workspace=workspace,
            ai=ai,
            vector_search=vector_search,
            jobs=jobs,
            knowledge_assistant=knowledge_assistant,
        ),
    )
