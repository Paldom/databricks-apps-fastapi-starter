import logging

import asyncpg

from app.core.config import Settings

logger = logging.getLogger("app")


async def create_pg_pool(settings: Settings) -> asyncpg.Pool:
    """Create and return an asyncpg connection pool."""
    logger.debug("Creating PostgreSQL pool")
    return await asyncpg.create_pool(
        host=settings.lakebase_host,
        port=settings.lakebase_port,
        database=settings.lakebase_db,
        user=settings.lakebase_user,
        password=settings.lakebase_password,
        min_size=1,
        max_size=4,
    )
