from contextlib import asynccontextmanager

from fastapi import FastAPI
from openai import AsyncOpenAI
from core.deps import get_workspace_client
from core.vector_search import init_vector_index, vector_index
from core.logging import setup_logging, get_logger

from config import settings
from fastapi_pagination import add_pagination

from api import api_router
from controllers import health
from core.database import init_pg_pool, close_pg_pool
from core.sqlalchemy import engine
from modules.base import Base as AppBase
import modules.users.models  # noqa: F401 – ensure AppUser is registered with Base.metadata
from middlewares import (
    authorization_middleware,
    security_headers_middleware,
    workspace_client_middleware,
)

setup_logging(settings.log_level)
logger = get_logger()

@asynccontextmanager
async def lifespan(app):
    logger.info("Starting application")
    logger.debug("Initialising PostgreSQL pool")
    await init_pg_pool()
    async with engine.begin() as conn:
        await conn.run_sync(AppBase.metadata.create_all)
    ws = get_workspace_client()
    cfg = ws.config
    app.state.ai_client = AsyncOpenAI(
        api_key=cfg.token,
        base_url=f"{cfg.host}/serving-endpoints",
        timeout=30.0,
    )
    init_vector_index()
    app.state.vector_index = vector_index
    try:
        yield
    finally:
        logger.debug("Closing AI client and database connections")
        await app.state.ai_client.aclose()
        await close_pg_pool()
        await engine.dispose()
        logger.info("Shutdown complete")


if settings.environment == "production":
    app = FastAPI(
        lifespan=lifespan,
        docs_url=None,
        openapi_url=None,
        redoc_url=None,
    )
else:
    app = FastAPI(lifespan=lifespan)


app.middleware("http")(authorization_middleware)
app.middleware("http")(workspace_client_middleware)
app.middleware("http")(security_headers_middleware)

app.include_router(health.router)
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router, prefix="/v1", include_in_schema=False)

add_pagination(app)
