"""FastAPI dependency providers for the database layer."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


async def get_async_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Provide a request-scoped session with an active transaction.

    The transaction commits when the request completes successfully,
    or rolls back on exception.  Repositories should ``flush()`` but
    never ``commit()`` — the commit happens here automatically.
    """
    factory = request.app.state.session_factory
    async with factory() as session:
        async with session.begin():
            yield session


def get_engine(request: Request) -> AsyncEngine:
    """Provide the async engine for lightweight operations (e.g. health checks)."""
    return request.app.state.engine
