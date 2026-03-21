"""Canonical database URL construction.

Both the runtime engine and Alembic migrations must use this single helper
so that the connection string is never duplicated or out of sync.
"""

from __future__ import annotations

import os

from sqlalchemy.engine import URL

from app.core.config import Settings


DATABASE_NOT_CONFIGURED_MESSAGE = (
    "DATABASE_URL or PG* settings are not configured"
)


def _build_asyncpg_url(
    *,
    username: str,
    password: str | None,
    host: str,
    port: int,
    database: str,
) -> str:
    return URL.create(
        drivername="postgresql+asyncpg",
        username=username,
        password=password or "",
        host=host,
        port=port,
        database=database,
    ).render_as_string(hide_password=False)


def get_database_url(settings: Settings) -> str:
    """Build an async PostgreSQL connection URL.

    Resolution order:
    1. ``DATABASE_URL`` environment variable (if set).
    2. Constructed from ``PG*`` settings (password is optional for
       Lakebase OAuth token flow).
    """
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit

    pg_host = getattr(settings, "pg_host", None)
    pg_database = getattr(settings, "pg_database", None)
    pg_user = getattr(settings, "pg_user", None)
    pg_password = getattr(settings, "pg_password", None)
    pg_port = getattr(settings, "pg_port", None) or 5432
    if all([pg_host, pg_database, pg_user]):
        return _build_asyncpg_url(
            username=pg_user,
            password=pg_password,
            host=pg_host,
            port=pg_port,
            database=pg_database,
        )

    raise ValueError(DATABASE_NOT_CONFIGURED_MESSAGE)
