from __future__ import annotations

from sqlalchemy import text

from app.core.config import Settings
from app.core.integrations import ensure_ai_client, ensure_vector_index, ensure_workspace_client
from app.core.runtime import AppRuntime
from app.models.health_dto import (
    DependencyCheck,
    DetailedHealthResponse,
    HealthStatus,
)


async def check_database(runtime: AppRuntime) -> DependencyCheck:
    if runtime.engine is None:
        return DependencyCheck(status=HealthStatus.FAIL, reason="Not configured")
    try:
        async with runtime.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return DependencyCheck(status=HealthStatus.OK)
    except Exception as exc:
        return DependencyCheck(status=HealthStatus.FAIL, reason=str(exc))


def check_workspace(runtime: AppRuntime, settings: Settings) -> DependencyCheck:
    if not settings.databricks_integrations_enabled():
        return DependencyCheck(status=HealthStatus.OK, reason="Disabled")
    try:
        ensure_workspace_client(runtime, settings)
        return DependencyCheck(status=HealthStatus.OK)
    except Exception as exc:
        return DependencyCheck(status=HealthStatus.FAIL, reason=str(exc))


def check_ai(runtime: AppRuntime, settings: Settings) -> DependencyCheck:
    if not settings.databricks_integrations_enabled():
        return DependencyCheck(status=HealthStatus.OK, reason="Disabled")
    if not settings.has_ai_config():
        return DependencyCheck(status=HealthStatus.OK, reason="Not configured")
    try:
        ensure_ai_client(runtime, settings)
        return DependencyCheck(status=HealthStatus.OK)
    except Exception as exc:
        return DependencyCheck(status=HealthStatus.FAIL, reason=str(exc))


def check_vector_search(runtime: AppRuntime, settings: Settings) -> DependencyCheck:
    if not settings.databricks_integrations_enabled():
        return DependencyCheck(status=HealthStatus.OK, reason="Disabled")
    if not settings.has_vector_search_config():
        return DependencyCheck(status=HealthStatus.OK, reason="Not configured")
    try:
        ensure_vector_index(runtime, settings)
        return DependencyCheck(status=HealthStatus.OK)
    except Exception as exc:
        return DependencyCheck(status=HealthStatus.FAIL, reason=str(exc))


async def build_detailed_health(
    runtime: AppRuntime,
    settings: Settings,
) -> DetailedHealthResponse:
    database = await check_database(runtime)
    workspace = check_workspace(runtime, settings)
    ai = check_ai(runtime, settings)
    vector_search = check_vector_search(runtime, settings)
    all_ok = all(
        c.status == HealthStatus.OK
        for c in [database, workspace, ai, vector_search]
    )
    return DetailedHealthResponse(
        ok=all_ok,
        database=database,
        workspace=workspace,
        ai=ai,
        vector_search=vector_search,
    )
