"""Tests for memory bootstrapping, message conversion, and checkpointer creation."""

from __future__ import annotations

import importlib
import logging
import types
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver

from app.chat.memory import (
    CheckpointerHandle,
    build_graph_input,
    convert_messages,
    create_checkpointer,
    create_checkpointer_async,
    has_checkpoint,
)


class TestConvertMessages:
    def test_user(self):
        result = convert_messages([{"role": "user", "content": "hi"}])
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "hi"

    def test_system(self):
        result = convert_messages([{"role": "system", "content": "sys"}])
        assert isinstance(result[0], SystemMessage)

    def test_assistant(self):
        result = convert_messages([{"role": "assistant", "content": "ok"}])
        assert isinstance(result[0], AIMessage)


class TestHasCheckpoint:
    @pytest.mark.asyncio
    async def test_returns_false_when_no_checkpoint(self):
        cp = MagicMock()
        cp.get.return_value = None
        assert await has_checkpoint(cp, "thread-1") is False

    @pytest.mark.asyncio
    async def test_returns_true_when_checkpoint_exists(self):
        cp = MagicMock()
        cp.get.return_value = {"some": "state"}
        assert await has_checkpoint(cp, "thread-1") is True

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self):
        cp = MagicMock()
        cp.get.side_effect = RuntimeError("boom")
        assert await has_checkpoint(cp, "thread-1") is False


class TestBuildGraphInput:
    @pytest.mark.asyncio
    async def test_bootstrap_full_history_when_no_checkpoint(self):
        cp = MagicMock()
        cp.get.return_value = None
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "how are you"},
        ]
        result = await build_graph_input(messages, "thread-new", cp)
        assert len(result["messages"]) == 3

    @pytest.mark.asyncio
    async def test_append_only_latest_user_when_checkpoint_exists(self):
        cp = MagicMock()
        cp.get.return_value = {"some": "state"}
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "how are you"},
        ]
        result = await build_graph_input(messages, "thread-existing", cp)
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "how are you"


# ---------------------------------------------------------------------------
# Checkpointer backend selection
# ---------------------------------------------------------------------------


def _make_settings(
    backend: str = "inmemory",
    *,
    has_db: bool = True,
    integrations: bool = False,
    pg_password: str | None = None,
) -> MagicMock:
    s = MagicMock()
    s.langgraph_memory_backend = backend
    s.has_database_config.return_value = has_db
    s.databricks_integrations_enabled.return_value = integrations
    s.pg_password = pg_password
    s.pg_app_schema = "starter"
    s.pg_host = "lakebase.example.com"
    s.pg_port = 5432
    s.pg_database = "appdb"
    s.pg_user = "app-sp"
    return s


def _fake_postgres_modules():
    """Fake psycopg_pool / langgraph.checkpoint.postgres.aio modules."""
    pools: list = []
    savers: list = []

    class FakeAsyncConnectionPool:
        @staticmethod
        async def check_connection(conn):  # referenced as the `check` callback
            return None

        def __init__(self, **kwargs):
            self.init_kwargs = kwargs
            self.open = AsyncMock()
            self.close = AsyncMock()
            pools.append(self)

    class FakeAsyncPostgresSaver:
        def __init__(self, conn):
            self.conn = conn
            self.setup = AsyncMock()
            savers.append(self)

    pool_mod = types.SimpleNamespace(AsyncConnectionPool=FakeAsyncConnectionPool)
    aio_mod = types.SimpleNamespace(AsyncPostgresSaver=FakeAsyncPostgresSaver)
    return pool_mod, aio_mod, pools, savers


def _patch_import_module(monkeypatch, mapping):
    """Route selected module names to fakes (or ImportError), pass through the rest."""
    real_import_module = importlib.import_module

    def fake_import_module(name, *args, **kwargs):
        if name in mapping:
            target = mapping[name]
            if isinstance(target, Exception):
                raise target
            return target
        return real_import_module(name, *args, **kwargs)

    monkeypatch.setattr("app.chat.memory.importlib.import_module", fake_import_module)


class TestCreateCheckpointer:
    def test_inmemory_default_returns_memory_saver(self):
        saver = create_checkpointer(_make_settings("inmemory"))
        assert isinstance(saver, MemorySaver)

    def test_lakebase_sync_falls_back_to_memory_saver_with_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="app"):
            saver = create_checkpointer(_make_settings("lakebase"))
        assert isinstance(saver, MemorySaver)
        assert "falling back to in-memory" in caplog.text


class TestCreateCheckpointerAsync:
    @pytest.mark.asyncio
    async def test_inmemory_returns_handle_with_memory_saver(self):
        handle = await create_checkpointer_async(_make_settings("inmemory"))
        assert isinstance(handle, CheckpointerHandle)
        assert isinstance(handle.saver, MemorySaver)
        assert handle.pool is None
        await handle.aclose()  # no-op

    @pytest.mark.asyncio
    async def test_lakebase_without_database_falls_back_with_warning(self, caplog):
        settings = _make_settings("lakebase", has_db=False)
        with caplog.at_level(logging.WARNING, logger="app"):
            handle = await create_checkpointer_async(settings)
        assert isinstance(handle.saver, MemorySaver)
        assert handle.pool is None
        assert "no database is configured" in caplog.text
        assert "falling back to in-memory" in caplog.text

    @pytest.mark.asyncio
    async def test_lakebase_missing_dependency_falls_back_with_warning(
        self, monkeypatch, caplog
    ):
        settings = _make_settings("lakebase")
        _patch_import_module(
            monkeypatch,
            {
                "langgraph.checkpoint.postgres.aio": ImportError(
                    "No module named 'langgraph.checkpoint.postgres'"
                )
            },
        )
        with caplog.at_level(logging.WARNING, logger="app"):
            handle = await create_checkpointer_async(settings)
        assert isinstance(handle.saver, MemorySaver)
        assert "langgraph-checkpoint-postgres" in caplog.text
        assert "falling back to in-memory" in caplog.text

    @pytest.mark.asyncio
    async def test_lakebase_local_static_credentials(self, monkeypatch):
        """DATABASE_URL (docker postgres) drives the conninfo; kwargs stay static."""
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://myuser:mypassword@127.0.0.1:5432/mydb",
        )
        settings = _make_settings("lakebase", integrations=False)
        pool_mod, aio_mod, pools, savers = _fake_postgres_modules()
        _patch_import_module(
            monkeypatch,
            {
                "psycopg_pool": pool_mod,
                "langgraph.checkpoint.postgres.aio": aio_mod,
            },
        )

        handle = await create_checkpointer_async(settings)

        assert len(pools) == 1 and len(savers) == 1
        pool, saver = pools[0], savers[0]
        assert handle.saver is saver
        assert handle.pool is pool
        assert saver.conn is pool
        assert (
            pool.init_kwargs["conninfo"]
            == "postgresql://myuser:mypassword@127.0.0.1:5432/mydb"
        )
        # Static credentials: plain dict kwargs, no token callable.
        assert pool.init_kwargs["kwargs"] == {
            "autocommit": True,
            "prepare_threshold": 0,
            "options": "-c search_path=starter,public",
        }
        assert pool.init_kwargs["open"] is False
        pool.open.assert_awaited_once()
        assert pool.open.await_args.kwargs["wait"] is True
        saver.setup.assert_awaited_once()

        await handle.aclose()
        pool.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lakebase_deployed_uses_fresh_token_per_connection(self, monkeypatch):
        """No static password + integrations on: kwargs is a per-connection callable."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        settings = _make_settings("lakebase", integrations=True, pg_password=None)
        pool_mod, aio_mod, pools, _ = _fake_postgres_modules()
        _patch_import_module(
            monkeypatch,
            {
                "psycopg_pool": pool_mod,
                "langgraph.checkpoint.postgres.aio": aio_mod,
            },
        )
        monkeypatch.setattr(
            "app.chat.memory._oauth_token_password", lambda: "fresh-token-123"
        )

        handle = await create_checkpointer_async(settings)

        pool = pools[0]
        assert (
            pool.init_kwargs["conninfo"]
            == "postgresql://app-sp:@lakebase.example.com:5432/appdb"
        )
        kwargs_param = pool.init_kwargs["kwargs"]
        assert callable(kwargs_param)
        resolved = await kwargs_param()
        assert resolved == {
            "autocommit": True,
            "prepare_threshold": 0,
            "options": "-c search_path=starter,public",
            "password": "fresh-token-123",
        }
        await handle.aclose()

    @pytest.mark.asyncio
    async def test_lakebase_setup_failure_falls_back_and_closes_pool(
        self, monkeypatch, caplog
    ):
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://myuser:mypassword@127.0.0.1:5432/mydb",
        )
        settings = _make_settings("lakebase")
        pool_mod, aio_mod, pools, _savers = _fake_postgres_modules()
        _patch_import_module(
            monkeypatch,
            {
                "psycopg_pool": pool_mod,
                "langgraph.checkpoint.postgres.aio": aio_mod,
            },
        )

        async def boom():
            raise RuntimeError("relation checkpoint_migrations is broken")

        with caplog.at_level(logging.WARNING, logger="app"):
            # Make setup() fail after the saver is constructed.
            original_init = aio_mod.AsyncPostgresSaver.__init__

            def failing_init(self, conn):
                original_init(self, conn)
                self.setup = AsyncMock(side_effect=boom)

            monkeypatch.setattr(aio_mod.AsyncPostgresSaver, "__init__", failing_init)
            handle = await create_checkpointer_async(settings)

        assert isinstance(handle.saver, MemorySaver)
        assert handle.pool is None
        assert "initialization failed" in caplog.text
        pools[0].close.assert_awaited_once()
