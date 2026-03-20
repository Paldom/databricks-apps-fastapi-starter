"""Async SQLAlchemy engine and session factory construction."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.db.url import get_database_url


def create_async_engine_from_settings(settings: Settings) -> AsyncEngine:
    """Create an async SQLAlchemy engine from application settings."""
    url = get_database_url(settings)
    return create_async_engine(url, echo=False, future=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to *engine*."""
    return async_sessionmaker(engine, expire_on_commit=False)
