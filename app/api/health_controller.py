import time
from logging import Logger
from typing import Annotated, Awaitable, Callable

from fastapi import APIRouter, Depends, Request, Response
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.databricks.vector_search import VectorSearchAdapter
from app.core.deps import get_logger, get_settings
from app.core.observability import (
    get_tracer,
    increment_counter,
    record_duration,
    tag_exception,
)
from app.core.runtime import get_app_runtime
from app.models.health_dto import (
    HealthCheckResult,
    HealthCheckStatus,
    HealthReport,
    HealthReportStatus,
)

router = APIRouter(tags=["Health"])

_tracer = get_tracer()

Probe = Callable[[], Awaitable[str]]


def _check(
    status: HealthCheckStatus,
    *,
    required: bool,
    message: str,
    latency_ms: float | None = None,
) -> HealthCheckResult:
    return HealthCheckResult(
        status=status,
        required=required,
        message=message,
        latency_ms=latency_ms,
    )


def _summarise_readiness(
    checks: dict[str, HealthCheckResult],
) -> tuple[bool, HealthReportStatus]:
    required_ok = all(
        check.status == HealthCheckStatus.OK
        for check in checks.values()
        if check.required
    )
    optional_ok = all(
        check.status == HealthCheckStatus.OK
        for check in checks.values()
        if not check.required
    )
    if not required_ok:
        return False, HealthReportStatus.NOT_READY
    if optional_ok:
        return True, HealthReportStatus.READY
    return True, HealthReportStatus.DEGRADED


async def _run_probe(
    name: str,
    *,
    required: bool,
    probe: Probe,
) -> HealthCheckResult:
    t0 = time.monotonic()
    with _tracer.start_as_current_span(f"health.check.{name}") as span:
        try:
            message = await probe()
            status = HealthCheckStatus.OK
            span.set_attribute("result", status.value)
            return _check(
                status,
                required=required,
                message=message,
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
            )
        except Exception as exc:
            status = HealthCheckStatus.FAIL
            tag_exception(span, exc)
            return _check(
                status,
                required=required,
                message=str(exc) or exc.__class__.__name__,
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
            )
        finally:
            elapsed = time.monotonic() - t0
            attrs = {"dependency": name, "result": status.value}
            record_duration("app.dependency.call.duration", elapsed, attrs)
            increment_counter("app.dependency.call.count", attributes=attrs)


async def _probe_database(engine: AsyncEngine) -> str:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return "SELECT 1 succeeded"


async def _probe_ai(client: AsyncOpenAI, endpoint: str) -> str:
    await client.embeddings.create(model=endpoint, input="ping")
    return "Embedding request succeeded"


async def _probe_vector(adapter: VectorSearchAdapter) -> str:
    await adapter.describe()
    return "Vector Search describe succeeded"


def _database_not_configured_message() -> str:
    return "DATABASE_URL or LAKEBASE_* settings are not configured"


def _ai_not_configured_message() -> str:
    return "SERVING_ENDPOINT_NAME is not set"


def _vector_not_configured_message() -> str:
    return (
        "VECTOR_SEARCH_ENDPOINT_NAME and VECTOR_SEARCH_INDEX_NAME are not set"
    )


def _optional_stub_message(name: str) -> str:
    return f"{name.capitalize()} integration is not configured"


async def _database_check(settings: Settings, request: Request) -> HealthCheckResult:
    runtime = get_app_runtime(request.app)
    if not settings.has_database_config() or runtime.engine is None:
        detail = runtime.error_for("database") or _database_not_configured_message()
        status = (
            HealthCheckStatus.FAIL
            if runtime.error_for("database")
            else HealthCheckStatus.NOT_CONFIGURED
        )
        return _check(status, required=True, message=detail)
    return await _run_probe(
        "database",
        required=True,
        probe=lambda: _probe_database(runtime.engine),
    )


async def _ai_check(
    settings: Settings,
    request: Request,
) -> HealthCheckResult:
    runtime = get_app_runtime(request.app)
    if not settings.has_ai_config():
        return _check(
            HealthCheckStatus.NOT_CONFIGURED,
            required=False,
            message=_ai_not_configured_message(),
        )
    if runtime.ai_client is None:
        return _check(
            HealthCheckStatus.FAIL,
            required=False,
            message=runtime.error_for("ai_client")
            or runtime.error_for("workspace_client")
            or "AI client is unavailable",
        )
    return await _run_probe(
        "ai",
        required=False,
        probe=lambda: _probe_ai(runtime.ai_client, settings.serving_endpoint_name),
    )


async def _vector_check(
    settings: Settings,
    request: Request,
    logger: Logger,
) -> HealthCheckResult:
    runtime = get_app_runtime(request.app)
    if not settings.has_vector_search_config():
        return _check(
            HealthCheckStatus.NOT_CONFIGURED,
            required=False,
            message=_vector_not_configured_message(),
        )
    if runtime.vector_index is None:
        return _check(
            HealthCheckStatus.FAIL,
            required=False,
            message=runtime.error_for("vector_index") or "Vector Search is unavailable",
        )
    adapter = VectorSearchAdapter(runtime.vector_index, logger)
    return await _run_probe(
        "vector_search",
        required=False,
        probe=lambda: _probe_vector(adapter),
    )


@router.get("/healthcheck", response_model=HealthReport)
@router.get("/health/live", response_model=HealthReport, include_in_schema=False)
async def live() -> HealthReport:
    return HealthReport(
        ok=True,
        status=HealthReportStatus.ALIVE,
        checks={
            "application": _check(
                HealthCheckStatus.OK,
                required=True,
                message="Application process is running",
            )
        },
    )


@router.get("/databasehealthcheck", response_model=HealthReport)
async def database_healthcheck(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthReport:
    db = await _database_check(settings, request)
    ok, status = _summarise_readiness({"database": db})
    report = HealthReport(ok=ok, status=status, checks={"database": db})
    response.status_code = 200 if ok else 503
    return report


@router.get("/health/ready", response_model=HealthReport)
async def ready(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> HealthReport:
    t0 = time.monotonic()
    with _tracer.start_as_current_span("health.ready"):
        logger.debug("Running readiness checks")

        checks = {
            "database": await _database_check(settings, request),
            "cache": _check(
                HealthCheckStatus.NOT_CONFIGURED,
                required=False,
                message=_optional_stub_message("cache"),
            ),
            "broker": _check(
                HealthCheckStatus.NOT_CONFIGURED,
                required=False,
                message=_optional_stub_message("broker"),
            ),
            "ai": await _ai_check(settings, request),
            "vector_search": await _vector_check(settings, request, logger),
        }

        ok, status = _summarise_readiness(checks)
        result = status.value
        elapsed = time.monotonic() - t0
        record_duration("app.health.readiness.duration", elapsed)
        increment_counter(
            "app.health.readiness.count", attributes={"result": result}
        )

    report = HealthReport(ok=ok, status=status, checks=checks)
    response.status_code = 200 if ok else 503
    return report
