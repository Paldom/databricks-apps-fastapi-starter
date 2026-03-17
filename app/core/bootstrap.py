import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from openai import AsyncOpenAI

from app.core.cache import build_cache
from app.core.config import settings
from app.core.databricks.vector_search import init_vector_index
from app.core.databricks.workspace import get_workspace_client_singleton
from app.core.db import create_async_engine_from_settings, create_session_factory
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
                logger.info("Database configuration not provided; skipping startup")

        with tracer.start_as_current_span("startup.workspace.client.init") as span:
            try:
                runtime.workspace_client = get_workspace_client_singleton()
                runtime.clear_error("workspace_client")
            except Exception as exc:
                tag_exception(span, exc)
                _record_startup_failure(runtime, "workspace_client", exc)

        with tracer.start_as_current_span("startup.ai.client.init") as span:
            if not settings.has_ai_config():
                logger.info("AI integration not configured; skipping startup")
            elif runtime.workspace_client is None:
                runtime.remember_error(
                    "ai_client",
                    runtime.error_for("workspace_client")
                    or "Databricks workspace client is unavailable",
                )
            else:
                try:
                    cfg = runtime.workspace_client.config
                    runtime.ai_client = AsyncOpenAI(
                        api_key=cfg.token,
                        base_url=f"{cfg.host}/serving-endpoints",
                        timeout=30.0,
                    )
                    runtime.clear_error("ai_client")
                except Exception as exc:
                    tag_exception(span, exc)
                    _record_startup_failure(runtime, "ai_client", exc)

        with tracer.start_as_current_span("startup.vector.index.init") as span:
            if not settings.has_vector_search_config():
                logger.info(
                    "Vector Search configuration not provided; skipping startup"
                )
            else:
                try:
                    runtime.vector_index = init_vector_index(settings)
                    runtime.clear_error("vector_index")
                except Exception as exc:
                    tag_exception(span, exc)
                    _record_startup_failure(runtime, "vector_index", exc)

        with tracer.start_as_current_span("startup.cache.init") as span:
            try:
                runtime.cache = build_cache(settings)
                runtime.clear_error("cache")
            except Exception as exc:
                tag_exception(span, exc)
                _record_startup_failure(runtime, "cache", exc)

    record_duration("app.startup.duration", time.monotonic() - t0)

    try:
        yield
    finally:
        # ── Shutdown ─────────────────────────────────────────────────
        t1 = time.monotonic()
        with tracer.start_as_current_span("app.shutdown") as shutdown_span:
            logger.debug("Closing AI client and database connections")
            try:
                if runtime.cache is not None:
                    with tracer.start_as_current_span("shutdown.cache.close"):
                        await runtime.cache.close()

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
