"""Short-term memory: checkpointer creation and input bootstrapping.

Thread-based memory semantics:
- First request (no checkpoint): seed the graph with full message history.
- Subsequent requests (checkpoint exists): append only the latest user message.

Lakebase (Postgres) checkpointer design
---------------------------------------
``LANGGRAPH_MEMORY_BACKEND=lakebase`` backs short-term memory with langgraph's
official ``AsyncPostgresSaver`` (``langgraph-checkpoint-postgres``, psycopg3)
on top of a ``psycopg_pool.AsyncConnectionPool`` so chat memory survives app
restarts.

Credential refresh: Lakebase passwords are short-lived OAuth tokens (~1h), so
a static connection string is not enough in production. The pool is created
with a *callable* ``kwargs`` (supported since psycopg-pool 3.3): psycopg_pool
awaits the callable for every **new physical connection**
(``AsyncConnectionPool._connect`` -> ``_resolve_kwargs``), and we mint a fresh
token there — the async twin of the SQLAlchemy ``do_connect`` hook in
``app.core.db.engine``. This was chosen over a custom ``connection_class``
subclass (equivalent, but more moving parts) and over the pool's ``configure``
hook (which runs *after* the connection is established — too late for
authentication).

Local dev: when ``DATABASE_URL`` carries static credentials (and Databricks
integrations are disabled), the conninfo derived from it is used as-is and no
token callable is installed.

Degradation: if the database is not configured, the optional dependency is
missing, or pool/migration setup fails, we log a warning and fall back to
``MemorySaver`` — startup must never crash (see AGENTS.md).

The optional dependencies (``langgraph-checkpoint-postgres``, ``psycopg``,
``psycopg-pool``) are imported lazily via ``importlib`` inside the lakebase
branch so the app and test suite work without them installed.
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger()

# Pool sizing/tuning for the checkpointer (kept intentionally small: chat
# checkpoint reads/writes are short and bursty).
_POOL_MIN_SIZE = 1
_POOL_MAX_SIZE = 5
_POOL_OPEN_TIMEOUT_SECONDS = 15.0


# Connection kwargs required by AsyncPostgresSaver: autocommit for its
# ``setup()`` migrations (e.g. CREATE INDEX CONCURRENTLY cannot run inside a
# transaction) and prepare_threshold=0 to stay safe behind connection proxies.
def _base_connect_kwargs(settings: Settings) -> dict[str, Any]:
    """Kwargs required by AsyncPostgresSaver, pinned to the app's schema.

    The checkpoint tables live next to the app's own tables (Lakebase denies
    CREATE in ``public`` to non-owners — see Settings.pg_app_schema).
    """
    return {
        "autocommit": True,
        "prepare_threshold": 0,
        "options": f"-c search_path={settings.pg_app_schema},public",
    }


@dataclass(slots=True)
class CheckpointerHandle:
    """A checkpointer plus the resources backing it.

    ``saver`` is what gets compiled into the LangGraph graph;
    ``aclose()`` releases the underlying connection pool (no-op for
    in-memory savers).
    """

    saver: Any
    pool: Any | None = None

    async def aclose(self) -> None:
        if self.pool is not None:
            await self.pool.close()


def create_checkpointer(settings: Settings) -> Any:
    """Create a checkpointer synchronously (request-time fallback path).

    The Lakebase saver needs an async lifecycle (pool open + ``setup()``)
    and is therefore created at startup by :func:`create_checkpointer_async`
    (see ``app.core.bootstrap``). Reaching this function with ``lakebase``
    configured means startup initialization did not run or failed; degrade
    to a process-local ``MemorySaver`` instead of failing the request.
    """
    if settings.langgraph_memory_backend == "lakebase":
        logger.warning(
            "Lakebase checkpointer unavailable in sync context (startup "
            "initialization missing or failed); falling back to in-memory "
            "checkpointer — chat memory will not survive restarts"
        )

    from langgraph.checkpoint.memory import MemorySaver

    logger.info("Using in-memory LangGraph checkpointer")
    return MemorySaver()


async def create_checkpointer_async(settings: Settings) -> CheckpointerHandle:
    """Create the configured checkpointer within a running event loop.

    Called from the app lifespan (``app.core.bootstrap``). The returned
    handle's ``aclose()`` must be awaited on shutdown.
    """
    if settings.langgraph_memory_backend == "lakebase":
        handle = await _create_lakebase_checkpointer(settings)
        if handle is not None:
            return handle

    from langgraph.checkpoint.memory import MemorySaver

    logger.info("Using in-memory LangGraph checkpointer")
    return CheckpointerHandle(saver=MemorySaver())


def _oauth_token_password() -> str:
    """Mint a fresh Lakebase password from the app's OAuth token.

    Mirrors the SQLAlchemy ``do_connect`` hook in ``app.core.db.engine``.
    """
    from databricks.sdk import WorkspaceClient

    token: str = WorkspaceClient().config.oauth_token().access_token
    return token


def _build_connect_kwargs(
    settings: Settings,
) -> dict[str, Any] | Callable[[], Awaitable[dict[str, Any]]]:
    """Connection kwargs for the pool: a static dict or per-connection callable.

    Deployed mode (Databricks integrations on, no static password): return an
    async callable — psycopg_pool awaits it for every new physical connection,
    so each one authenticates with a freshly minted OAuth token. Otherwise
    (local docker postgres via ``DATABASE_URL``) the static kwargs suffice and
    credentials come from the conninfo itself.
    """
    if not settings.databricks_integrations_enabled() or settings.pg_password:
        return _base_connect_kwargs(settings)

    async def _kwargs_with_fresh_token() -> dict[str, Any]:
        password = await asyncio.to_thread(_oauth_token_password)
        return {**_base_connect_kwargs(settings), "password": password}

    return _kwargs_with_fresh_token


async def _create_lakebase_checkpointer(
    settings: Settings,
) -> CheckpointerHandle | None:
    """Build an ``AsyncPostgresSaver`` on a token-refreshing psycopg pool.

    Returns ``None`` (caller falls back to in-memory) when the database is
    not configured, the optional dependencies are missing, or pool/migration
    setup fails.
    """
    if not settings.has_database_config():
        logger.warning(
            "LANGGRAPH_MEMORY_BACKEND=lakebase but no database is configured "
            "(set DATABASE_URL or PGHOST/PGDATABASE/PGUSER); "
            "falling back to in-memory checkpointer"
        )
        return None

    try:
        aio_mod = importlib.import_module("langgraph.checkpoint.postgres.aio")
        pool_mod = importlib.import_module("psycopg_pool")
    except ImportError:
        logger.warning(
            "LANGGRAPH_MEMORY_BACKEND=lakebase requires the optional "
            "'langgraph-checkpoint-postgres' dependency (with psycopg and "
            "psycopg-pool); falling back to in-memory checkpointer"
        )
        return None

    from app.core.db.url import get_psycopg_database_url

    conninfo = get_psycopg_database_url(settings)
    pool = pool_mod.AsyncConnectionPool(
        conninfo=conninfo,
        kwargs=_build_connect_kwargs(settings),
        min_size=_POOL_MIN_SIZE,
        max_size=_POOL_MAX_SIZE,
        open=False,
        # Validate pooled connections at checkout so server-side idle
        # disconnects (common with managed Postgres) are healed transparently.
        check=pool_mod.AsyncConnectionPool.check_connection,
        name="langgraph-checkpointer",
    )
    try:
        await pool.open(wait=True, timeout=_POOL_OPEN_TIMEOUT_SECONDS)
        saver = aio_mod.AsyncPostgresSaver(pool)
        await saver.setup()  # idempotent checkpoint-table migrations
    except Exception as exc:
        logger.warning(
            "Lakebase checkpointer initialization failed (%s); "
            "falling back to in-memory checkpointer",
            exc,
        )
        try:
            await pool.close()
        except Exception:  # pragma: no cover - best-effort cleanup
            logger.debug("Failed to close checkpointer pool", exc_info=True)
        return None

    logger.info("Using Lakebase (Postgres) LangGraph checkpointer")
    return CheckpointerHandle(saver=saver, pool=pool)


# ---------------------------------------------------------------------------
# Message conversion
# ---------------------------------------------------------------------------


def _convert_message(msg: dict[str, Any]) -> HumanMessage | SystemMessage | AIMessage:
    role = msg.get("role", "user")
    content = msg.get("content", "")
    if role == "system":
        return SystemMessage(content=content)
    if role == "assistant":
        return AIMessage(content=content)
    return HumanMessage(content=content)


def convert_messages(
    messages: list[dict[str, Any]],
) -> list[HumanMessage | SystemMessage | AIMessage]:
    return [_convert_message(m) for m in messages]


# ---------------------------------------------------------------------------
# Checkpoint-aware input builder
# ---------------------------------------------------------------------------


def _latest_user_message(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg
    return None


async def has_checkpoint(checkpointer: Any, thread_id: str) -> bool:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        checkpoint = await asyncio.to_thread(checkpointer.get, config)
        return checkpoint is not None
    except Exception:
        logger.debug(
            "Error checking checkpoint for thread %s", thread_id, exc_info=True
        )
        return False


async def build_graph_input(
    messages: list[dict[str, Any]],
    thread_id: str,
    checkpointer: Any,
) -> dict[str, Any]:
    """Build the input state for the agent.

    - No checkpoint: seed with full history.
    - Checkpoint exists: append only the latest user message.
    """
    has_state = await has_checkpoint(checkpointer, thread_id)

    if not has_state:
        logger.debug(
            "No checkpoint for thread %s; bootstrapping with full history", thread_id
        )
        return {"messages": convert_messages(messages)}

    latest = _latest_user_message(messages)
    if latest is None:
        logger.warning(
            "Checkpoint exists for thread %s but no user message found", thread_id
        )
        return {"messages": []}

    logger.debug(
        "Checkpoint exists for thread %s; appending latest user message", thread_id
    )
    return {"messages": convert_messages([latest])}
