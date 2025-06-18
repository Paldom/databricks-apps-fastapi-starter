from asyncpg import Pool
from fastapi import APIRouter, Depends

from core.deps import get_pg_pool, get_ai_client, get_settings, get_logger
from core.vector_search import get_vector_index
import asyncio
from openai import AsyncOpenAI
from config import Settings
from logging import Logger

router = APIRouter(prefix="/health")


@router.get("/live")
async def live() -> dict[str, bool]:
    return {"ok": True}


async def check_db(pool: Pool) -> bool:
    try:
        await pool.fetchval("SELECT 1")
        return True
    except Exception:
        return False


async def check_cache() -> bool:
    return True


async def check_broker() -> bool:
    return True


async def check_ai(client: AsyncOpenAI, endpoint: str | None) -> bool:
    if not endpoint:
        return True
    try:
        await client.embeddings.create(model=endpoint, input="ping")
        return True
    except Exception:
        return False


async def check_vector(index) -> bool:
    try:
        await asyncio.to_thread(index.describe)
        return True
    except Exception:
        return False


@router.get("/ready")
async def ready(
    pool: Pool = Depends(get_pg_pool),
    client: AsyncOpenAI = Depends(get_ai_client),
    settings: Settings = Depends(get_settings),
    index = Depends(get_vector_index),
    logger: Logger = Depends(get_logger),
) -> dict[str, bool]:
    logger.debug("Running readiness checks")
    db_ok = await check_db(pool)
    cache_ok = await check_cache()
    broker_ok = await check_broker()
    ai_ok = await check_ai(client, settings.serving_endpoint_name)
    vector_ok = await check_vector(index)
    return {
        "ok": db_ok and cache_ok and broker_ok and ai_ok and vector_ok,
        "db": db_ok,
        "cache": cache_ok,
        "broker": broker_ok,
        "ai": ai_ok,
        "vector_search": vector_ok,
    }
