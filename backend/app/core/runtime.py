from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from databricks.sdk import WorkspaceClient
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@dataclass(slots=True)
class AppRuntime:
    engine: AsyncEngine | None = None
    session_factory: async_sessionmaker[AsyncSession] | None = None
    workspace_client: WorkspaceClient | None = None
    ai_client: AsyncOpenAI | None = None
    vector_index: Any | None = None
    langgraph_checkpointer: Any | None = None


def get_app_runtime(container: Any) -> AppRuntime:
    runtime = getattr(container.state, "runtime", None)
    if runtime is None:
        runtime = AppRuntime()
        container.state.runtime = runtime
    return runtime
