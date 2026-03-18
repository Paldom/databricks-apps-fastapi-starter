from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from databricks.sdk import WorkspaceClient
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from app.core.cache import Cache


@dataclass(slots=True)
class AppRuntime:
    engine: AsyncEngine | None = None
    session_factory: async_sessionmaker[AsyncSession] | None = None
    workspace_client: WorkspaceClient | None = None
    ai_client: AsyncOpenAI | None = None
    vector_index: Any | None = None
    cache: Cache | None = None
    resource_states: dict[str, str] = field(default_factory=dict)
    init_errors: dict[str, str] = field(default_factory=dict)
    last_deep_health: Any = None
    last_deep_health_at: float = 0.0

    def remember_error(self, name: str, exc: Exception | str) -> None:
        message = exc if isinstance(exc, str) else str(exc)
        self.resource_states[name] = "fail"
        self.init_errors[name] = message or exc.__class__.__name__

    def clear_error(self, name: str) -> None:
        self.resource_states[name] = "ok"
        self.init_errors.pop(name, None)

    def error_for(self, name: str) -> str | None:
        return self.init_errors.get(name)

    def disable(self, name: str, reason: str) -> None:
        self.resource_states[name] = "disabled"
        self.init_errors[name] = reason

    def not_configured(self, name: str, reason: str) -> None:
        self.resource_states[name] = "not_configured"
        self.init_errors[name] = reason

    def state_for(self, name: str) -> str | None:
        return self.resource_states.get(name)


def get_app_runtime(container: Any) -> AppRuntime:
    runtime = getattr(container.state, "runtime", None)
    if runtime is None:
        runtime = AppRuntime()
        container.state.runtime = runtime
    return runtime
