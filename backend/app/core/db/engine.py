"""Async SQLAlchemy engine and session factory construction."""

from __future__ import annotations

import logging

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
    """Create an async SQLAlchemy engine from application settings.

    When Databricks integrations are enabled and no explicit password is
    configured, the engine authenticates to Lakebase using the app's OAuth
    token via ``WorkspaceClient``.  This follows the official Databricks
    pattern (see ``bundle-examples/app_with_database``).
    """
    url = get_database_url(settings)
    engine = create_async_engine(url, echo=False, future=True)

    if settings.databricks_integrations_enabled() and not settings.pg_password:
        _register_oauth_token_provider(engine.sync_engine)

    return engine


def _register_oauth_token_provider(sync_engine) -> None:  # type: ignore[no-untyped-def]
    """Provide the app's OAuth token as the database password on each connect."""

    @event.listens_for(sync_engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):  # type: ignore[no-untyped-def]
        try:
            from databricks.sdk import WorkspaceClient

            w = WorkspaceClient()
            cparams["password"] = w.config.oauth_token().access_token
        except Exception:
            logger.debug("OAuth token refresh failed", exc_info=True)

    logger.info("Lakebase OAuth token provider registered")


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to *engine*."""
    return async_sessionmaker(engine, expire_on_commit=False)
