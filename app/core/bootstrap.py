import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.db import create_async_engine_from_settings, create_session_factory
from app.core.integrations import initialise_optional_resource_states
from app.core.logging import get_logger, setup_logging
from app.core.observability import get_tracer, record_duration, tag_exception
from app.core.runtime import AppRuntime
import app.models  # noqa: F401 – register all models with Base.metadata

setup_logging(settings.log_level)
logger = get_logger()


def _record_startup_failure(runtime: AppRuntime, name: str, exc: Exception) -> None:
    runtime.remember_error(name, exc)
    logger.warning("Startup initialisation for %s failed: %s", name, exc)


@asynccontextmanager
async def lifespan(application: FastAPI):
    tracer = get_tracer()
    runtime = AppRuntime()
    application.state.runtime = runtime

    # Propagate runtime to mounted sub-apps (e.g. /api)
    for route in application.routes:
        sub = getattr(route, "app", None)
        if sub is not None and hasattr(sub, "state"):
            sub.state.runtime = runtime

    # ── Startup ──────────────────────────────────────────────────────
    t0 = time.monotonic()
    with tracer.start_as_current_span("app.startup"):
        logger.info("Starting application")

        with tracer.start_as_current_span("startup.db.pool.init") as span:
            if settings.has_database_config():
                try:
                    runtime.engine = create_async_engine_from_settings(settings)
                    runtime.session_factory = create_session_factory(runtime.engine)
                    runtime.clear_error("database")
                except Exception as exc:
                    tag_exception(span, exc)
                    _record_startup_failure(runtime, "database", exc)
            else:
                runtime.not_configured(
                    "database",
                    "DATABASE_URL, PG*, or LAKEBASE_* settings are not configured",
                )
                logger.info("Database configuration not provided; skipping startup")

        initialise_optional_resource_states(runtime, settings)

    record_duration("app.startup.duration", time.monotonic() - t0)

    try:
        yield
    finally:
        # ── Shutdown ─────────────────────────────────────────────────
        t1 = time.monotonic()
        with tracer.start_as_current_span("app.shutdown") as shutdown_span:
            logger.debug("Closing AI client and database connections")
            try:
                if runtime.ai_client is not None:
                    with tracer.start_as_current_span("shutdown.ai.client.close"):
                        await runtime.ai_client.aclose()

                if runtime.engine is not None:
                    with tracer.start_as_current_span("shutdown.db.pool.close"):
                        await runtime.engine.dispose()

            except Exception as exc:
                tag_exception(shutdown_span, exc)
                raise
            finally:
                record_duration("app.shutdown.duration", time.monotonic() - t1)
                logger.info("Shutdown complete")
