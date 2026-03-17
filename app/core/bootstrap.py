import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.databricks.vector_search import init_vector_index
from app.core.databricks.workspace import get_workspace_client_singleton
from app.core.db import create_async_engine_from_settings, create_session_factory
from app.core.logging import get_logger, setup_logging
from app.core.observability import get_tracer, record_duration, tag_exception
import app.models  # noqa: F401 – register all models with Base.metadata

setup_logging(settings.log_level)
logger = get_logger()


@asynccontextmanager
async def lifespan(application: FastAPI):
    tracer = get_tracer()

    # ── Startup ──────────────────────────────────────────────────────
    t0 = time.monotonic()
    with tracer.start_as_current_span("app.startup") as startup_span:
        logger.info("Starting application")
        try:
            with tracer.start_as_current_span("startup.db.pool.init"):
                engine = create_async_engine_from_settings(settings)
                application.state.engine = engine
                application.state.session_factory = create_session_factory(engine)

            with tracer.start_as_current_span("startup.ai.client.init"):
                ws = get_workspace_client_singleton()
                cfg = ws.config
                application.state.ai_client = AsyncOpenAI(
                    api_key=cfg.token,
                    base_url=f"{cfg.host}/serving-endpoints",
                    timeout=30.0,
                )

            with tracer.start_as_current_span("startup.vector.index.init"):
                application.state.vector_index = init_vector_index(settings)

        except Exception as exc:
            tag_exception(startup_span, exc)
            raise

    record_duration("app.startup.duration", time.monotonic() - t0)

    try:
        yield
    finally:
        # ── Shutdown ─────────────────────────────────────────────────
        t1 = time.monotonic()
        with tracer.start_as_current_span("app.shutdown") as shutdown_span:
            logger.debug("Closing AI client and database connections")
            try:
                with tracer.start_as_current_span("shutdown.ai.client.close"):
                    await application.state.ai_client.aclose()

                with tracer.start_as_current_span("shutdown.db.pool.close"):
                    await engine.dispose()

            except Exception as exc:
                tag_exception(shutdown_span, exc)
                raise
            finally:
                record_duration("app.shutdown.duration", time.monotonic() - t1)
                logger.info("Shutdown complete")
