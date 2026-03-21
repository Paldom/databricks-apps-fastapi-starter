import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.db import create_async_engine_from_settings, create_session_factory
from app.core.logging import get_logger, setup_logging
from app.core.observability import get_tracer, tag_exception
from app.core.runtime import AppRuntime
import app.models  # noqa: F401 – register all models with Base.metadata

setup_logging(settings.log_level)
logger = get_logger()


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
    with tracer.start_as_current_span("app.startup") as startup_span:
        logger.info("Starting application")

        with tracer.start_as_current_span("startup.db.pool.init") as span:
            if settings.has_database_config():
                try:
                    runtime.engine = create_async_engine_from_settings(settings)
                    runtime.session_factory = create_session_factory(runtime.engine)
                except Exception as exc:
                    tag_exception(span, exc)
                    logger.warning("Database initialization failed: %s", exc)
            else:
                logger.info("Database configuration not provided; skipping")

        # ── MLflow tracing ─────────────────────────────────────────
        try:
            _init_mlflow_tracing()
        except Exception as exc:
            logger.debug("MLflow tracing init failed: %s", exc)

        # ── LangGraph checkpointer ───────────────────────────────
        try:
            from app.chat.memory import create_checkpointer

            runtime.langgraph_checkpointer = create_checkpointer(settings)
        except ImportError:
            logger.warning("LangGraph not installed; skipping checkpointer init")
        except Exception as exc:
            logger.warning("LangGraph checkpointer init failed: %s", exc)

        startup_span.set_attribute("duration_s", time.monotonic() - t0)

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
                shutdown_span.set_attribute("duration_s", time.monotonic() - t1)
                logger.info("Shutdown complete")


def _init_mlflow_tracing() -> None:
    """Bootstrap MLflow tracing if an experiment ID is configured."""
    import os

    experiment_id = os.getenv("MLFLOW_EXPERIMENT_ID")
    if not experiment_id:
        logger.info("MLFLOW_EXPERIMENT_ID not set; MLflow tracing is disabled")
        return

    import mlflow

    mlflow.set_experiment(experiment_id=experiment_id)
    mlflow.langchain.autolog()
    logger.info("MLflow LangChain autolog enabled (experiment=%s)", experiment_id)
    try:
        mlflow.openai.autolog()
    except Exception:
        logger.debug("MLflow OpenAI autolog unavailable", exc_info=True)
