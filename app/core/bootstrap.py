from contextlib import asynccontextmanager

from fastapi import FastAPI
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.databricks.vector_search import init_vector_index
from app.core.databricks.workspace import get_workspace_client_singleton
from app.core.db import create_async_engine_from_settings, create_session_factory
from app.core.logging import get_logger, setup_logging
import app.models  # noqa: F401 – register all models with Base.metadata

setup_logging(settings.log_level)
logger = get_logger()


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Starting application")

    # Database — Alembic owns the schema; runtime only opens connections.
    engine = create_async_engine_from_settings(settings)
    application.state.engine = engine
    application.state.session_factory = create_session_factory(engine)

    # Databricks resources
    ws = get_workspace_client_singleton()
    cfg = ws.config
    application.state.ai_client = AsyncOpenAI(
        api_key=cfg.token,
        base_url=f"{cfg.host}/serving-endpoints",
        timeout=30.0,
    )
    application.state.vector_index = init_vector_index(settings)

    try:
        yield
    finally:
        logger.debug("Closing AI client and database connections")
        await application.state.ai_client.aclose()
        await engine.dispose()
        logger.info("Shutdown complete")
