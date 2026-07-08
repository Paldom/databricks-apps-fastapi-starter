from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from databricks.sdk import WorkspaceClient
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from app.chat.memory import CheckpointerHandle


@dataclass(slots=True)
class AppRuntime:
    engine: AsyncEngine | None = None
    session_factory: async_sessionmaker[AsyncSession] | None = None
    workspace_client: WorkspaceClient | None = None
    ai_client: AsyncOpenAI | None = None
    vector_index: Any | None = None
    langgraph_checkpointer: Any | None = None
    # Owns the saver's backing resources (e.g. the Lakebase connection pool);
    # created in the lifespan and closed on shutdown (see app.core.bootstrap).
    langgraph_checkpointer_handle: CheckpointerHandle | None = None


def get_app_runtime(container: Any) -> AppRuntime:
    runtime = getattr(container.state, "runtime", None)
    if runtime is None:
        runtime = AppRuntime()
        container.state.runtime = runtime
    return runtime
