"""Databricks Apps entrypoint.

When deployed via ``databricks bundle``, the app source root is ``backend/``
(set via ``source_code_path: ./backend`` in the bundle resource).  The working
directory is therefore ``backend/``, so ``app.*`` imports resolve without any
path manipulation.

Migrations run automatically on every deploy/restart — there is no separate
migration step.
"""
from __future__ import annotations

import logging
import os

import uvicorn

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """Run pending Alembic migrations before the server starts.

    Uses the same engine factory as the app, which includes the OAuth
    ``do_connect`` hook for Lakebase authentication when deployed.
    Failures are logged but do not prevent the server from starting —
    this allows health endpoints to respond so the platform can report
    the real error.
    """
    try:
        from alembic import command as alembic_command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        alembic_command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed")
    except Exception as exc:
        logger.warning("Database migrations failed: %s", exc)


def run_server() -> None:
    """Start the uvicorn server."""
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("DATABRICKS_APP_PORT", os.environ.get("UVICORN_PORT", "8000"))),
        log_level=os.environ.get("UVICORN_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    run_migrations()
    run_server()
