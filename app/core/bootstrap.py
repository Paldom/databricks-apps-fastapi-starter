from contextlib import asynccontextmanager

from fastapi import FastAPI
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.database import create_pg_pool
from app.core.databricks.vector_search import init_vector_index
from app.core.databricks.workspace import get_workspace_client_singleton
from app.core.logging import get_logger, setup_logging
from app.core.sqlalchemy import create_engine, create_session_factory
from app.models.base import Base
import app.models.user_model  # noqa: F401 – register AppUser with metadata
import app.models.todo_model  # noqa: F401 – register Todo with metadata

setup_logging(settings.log_level)
logger = get_logger()


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Starting application")

    # Database
    logger.debug("Initialising PostgreSQL pool")
    application.state.pg_pool = await create_pg_pool(settings)

    engine = create_engine(settings)
    application.state.engine = engine
    application.state.session_factory = create_session_factory(engine)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
        await application.state.pg_pool.close()
        await engine.dispose()
        logger.info("Shutdown complete")
