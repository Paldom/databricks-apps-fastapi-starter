from __future__ import annotations

import asyncio
import logging

from alembic import context
from sqlalchemy import text
from app.core.config import settings
from app.core.db.base import Base
from app.core.db.engine import create_async_engine_from_settings
import app.models  # noqa: F401 – register all models with Base.metadata

config = context.config
target_metadata = Base.metadata

# Every app instance migrates on start; the transaction-scoped advisory lock serialises
# them so a second instance waits and then finds the schema already at head.
MIGRATION_LOCK_KEY = 8_213_047_001
LOCK_TIMEOUT = "120s"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    from app.core.db.url import get_database_url

    url = get_database_url(settings)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=settings.db_schema,
    )
    with context.begin_transaction():
        connection.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
        connection.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY}
        ).scalar()
        logging.getLogger("alembic.runtime.migration").info(
            "Migration advisory lock acquired (key=%s)", MIGRATION_LOCK_KEY
        )
        # The connecting identity becomes the owner; search_path points here.
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.db_schema}"'))
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations through the app's engine (same OAuth hook as the app)."""
    connectable = create_async_engine_from_settings(settings)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
