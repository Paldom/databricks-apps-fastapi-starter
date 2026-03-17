"""Canonical database URL construction.

Both the runtime engine and Alembic migrations must use this single helper
so that the connection string is never duplicated or out of sync.
"""

from __future__ import annotations

import os

from app.core.config import Settings


def get_database_url(settings: Settings) -> str:
    """Build an async PostgreSQL connection URL.

    Resolution order:
    1. ``DATABASE_URL`` environment variable (if set).
    2. Constructed from ``settings.lakebase_*`` fields.
    """
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit

    return (
        f"postgresql+asyncpg://{settings.lakebase_user}:{settings.lakebase_password}"
        f"@{settings.lakebase_host}:{settings.lakebase_port}/{settings.lakebase_db}"
    )
