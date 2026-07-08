"""Integration test for the Lakebase (Postgres) LangGraph checkpointer.

Runs only when the optional postgres checkpointer dependencies
(``langgraph-checkpoint-postgres``, ``psycopg``) are installed AND a local
Postgres (``make dev-db``, see ``backend/env.example``) is reachable;
otherwise the whole module is skipped.
"""

from __future__ import annotations

import os
import socket
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.engine import make_url

_DEFAULT_LOCAL_URL = "postgresql+asyncpg://myuser:mypassword@127.0.0.1:5432/mydb"
_DATABASE_URL = os.environ.get("DATABASE_URL", _DEFAULT_LOCAL_URL)


def _postgres_reachable(url: str) -> bool:
    try:
        parsed = make_url(url)
        host = parsed.host or "127.0.0.1"
        port = parsed.port or 5432
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


pytest.importorskip("psycopg", reason="psycopg not installed")
# Module object is used below instead of a direct import so mypy stays clean
# while the optional dependency is not installed.
_postgres_aio = pytest.importorskip(
    "langgraph.checkpoint.postgres.aio",
    reason="langgraph-checkpoint-postgres not installed",
)

pytestmark = pytest.mark.skipif(
    not _postgres_reachable(_DATABASE_URL),
    reason="local postgres is not reachable (start it with `make dev-db`)",
)


@pytest.mark.asyncio
async def test_lakebase_checkpointer_roundtrip(monkeypatch):
    """End-to-end: pool + setup() migrations + checkpoint put/get roundtrip."""
    from langgraph.checkpoint.base import empty_checkpoint

    from app.chat.memory import create_checkpointer_async, has_checkpoint

    AsyncPostgresSaver = _postgres_aio.AsyncPostgresSaver

    monkeypatch.setenv("DATABASE_URL", _DATABASE_URL)
    settings = MagicMock()
    settings.langgraph_memory_backend = "lakebase"
    settings.has_database_config.return_value = True
    settings.databricks_integrations_enabled.return_value = False
    settings.pg_password = None

    handle = await create_checkpointer_async(settings)
    try:
        saver = handle.saver
        assert isinstance(saver, AsyncPostgresSaver), (
            f"expected the real Postgres saver, got a fallback: {type(saver).__name__}"
        )

        thread_id = f"integration-{uuid.uuid4()}"
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        checkpoint = empty_checkpoint()

        # The sync-from-thread path used by build_graph_input must work too.
        assert await has_checkpoint(saver, thread_id) is False

        await saver.aput(config, checkpoint, {"source": "input", "step": -1}, {})

        assert await has_checkpoint(saver, thread_id) is True
        saved = await saver.aget_tuple(config)
        assert saved is not None
        assert saved.checkpoint["id"] == checkpoint["id"]
    finally:
        await handle.aclose()
