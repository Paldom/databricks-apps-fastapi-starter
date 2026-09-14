"""Async SQLAlchemy engine and session factory construction."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.db.url import get_database_url

logger = logging.getLogger(__name__)


def create_async_engine_from_settings(settings: Settings) -> AsyncEngine:
    """Engine for local Postgres or Lakebase.

    Lakebase: the password is the app's OAuth token, supplied on every physical
    connect (tokens expire hourly, so ``pool_recycle`` stays below that), TLS is
    required, and ``pool_pre_ping`` reconnects after the endpoint resumes from
    scale-to-zero.
    """
    connect_args: dict[str, Any] = {
        "server_settings": {"search_path": settings.db_schema},
    }
    if settings.pg_sslmode == "require":
        connect_args["ssl"] = "require"
    engine = create_async_engine(
        get_database_url(settings),
        pool_pre_ping=True,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        connect_args=connect_args,
    )
    if settings.databricks_integrations_enabled() and not settings.pg_password:
        _register_oauth_token_provider(engine.sync_engine)
    return engine


def _register_oauth_token_provider(sync_engine: Any) -> None:
    """Use the app's OAuth token as the database password on each connect."""
    from databricks.sdk import WorkspaceClient

    workspace = WorkspaceClient()  # one client; the SDK caches and refreshes the token

    @event.listens_for(sync_engine, "do_connect")
    def provide_token(
        dialect: Any, conn_rec: Any, cargs: Any, cparams: dict[str, Any]
    ) -> None:
        cparams["password"] = workspace.config.oauth_token().access_token

    logger.info("Lakebase OAuth token provider registered")


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
