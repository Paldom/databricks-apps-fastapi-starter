"""FastAPI dependency providers for the database layer."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.errors import ConfigurationError, ServiceUnavailableError
from app.core.runtime import get_app_runtime


async def get_async_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Provide a request-scoped session with an active transaction.

    The transaction commits when the request completes successfully,
    or rolls back on exception.  Repositories should ``flush()`` but
    never ``commit()`` — the commit happens here automatically.
    """
    runtime = get_app_runtime(request.app)
    factory = runtime.session_factory
    if factory is None:
        detail = runtime.error_for("database")
        if detail:
            raise ServiceUnavailableError(f"Database is unavailable: {detail}")
        raise ConfigurationError("Database is not configured")
    async with factory() as session:
        async with session.begin():
            yield session


def get_engine(request: Request) -> AsyncEngine:
    """Provide the async engine for lightweight operations (e.g. health checks)."""
    runtime = get_app_runtime(request.app)
    engine = runtime.engine
    if engine is None:
        detail = runtime.error_for("database")
        if detail:
            raise ServiceUnavailableError(f"Database is unavailable: {detail}")
        raise ConfigurationError("Database is not configured")
    return engine
