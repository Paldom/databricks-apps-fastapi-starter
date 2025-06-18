import asyncpg
import logging
from typing import Optional

from config import settings

LAKEBASE_DSN = {
    "host": settings.lakebase_host,
    "port": settings.lakebase_port,
    "database": settings.lakebase_db,
    "user": settings.lakebase_user,
    "password": settings.lakebase_password,
}

pg_pool: Optional[asyncpg.Pool] = None

async def init_pg_pool() -> None:
    global pg_pool
    logging.getLogger("app").debug("Creating PostgreSQL pool")
    pg_pool = await asyncpg.create_pool(**LAKEBASE_DSN, min_size=1, max_size=4)

async def close_pg_pool() -> None:
    if pg_pool:
        logging.getLogger("app").debug("Closing PostgreSQL pool")
        await pg_pool.close()
