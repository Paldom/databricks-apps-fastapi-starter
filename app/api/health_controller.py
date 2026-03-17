from logging import Logger
from typing import Annotated

from fastapi import APIRouter, Depends
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.deps import get_ai_client, get_engine, get_logger, get_settings, get_vector_search_adapter
from app.core.databricks.vector_search import VectorSearchAdapter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
async def live() -> dict[str, bool]:
    return {"ok": True}


async def _check_db(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_cache() -> bool:
    return True


def _check_broker() -> bool:
    return True


async def _check_ai(client: AsyncOpenAI, endpoint: str | None) -> bool:
    if not endpoint:
        return True
    try:
        await client.embeddings.create(model=endpoint, input="ping")
        return True
    except Exception:
        return False


async def _check_vector(adapter: VectorSearchAdapter) -> bool:
    try:
        await adapter.describe()
        return True
    except Exception:
        return False


@router.get("/ready")
async def ready(
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    client: Annotated[AsyncOpenAI, Depends(get_ai_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    vs_adapter: Annotated[VectorSearchAdapter, Depends(get_vector_search_adapter)],
    logger: Annotated[Logger, Depends(get_logger)],
) -> dict[str, bool]:
    logger.debug("Running readiness checks")
    db_ok = await _check_db(engine)
    cache_ok = _check_cache()
    broker_ok = _check_broker()
    ai_ok = await _check_ai(client, settings.serving_endpoint_name)
    vector_ok = await _check_vector(vs_adapter)
    return {
        "ok": db_ok and cache_ok and broker_ok and ai_ok and vector_ok,
        "db": db_ok,
        "cache": cache_ok,
        "broker": broker_ok,
        "ai": ai_ok,
        "vector_search": vector_ok,
    }
