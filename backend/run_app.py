"""Databricks Apps entrypoint: migrate, then serve.

The bundle sets ``source_code_path`` to ``backend/``, so this runs with ``backend/`` as
the working directory. Migrations run on every start; a failed migration stops the
process so the platform reports the error instead of a half-migrated app that looks
healthy.
"""

from __future__ import annotations

import logging
import os

import uvicorn

from app.core.config import settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    if not settings.has_database_config():
        logger.warning("No database configured; skipping migrations")
        return
    from alembic import command as alembic_command
    from alembic.config import Config

    alembic_command.upgrade(Config("alembic.ini"), "head")
    logger.info("Database migrations completed")


def run_server() -> None:
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # nosec B104 - the Apps proxy is the only client of this port
        port=int(os.environ.get("DATABRICKS_APP_PORT", "8000")),
        log_level=os.environ.get("UVICORN_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    setup_logging(
        settings.log_level
    )  # before migrations: the OTel log format needs the envelope fields
    run_migrations()
    run_server()
