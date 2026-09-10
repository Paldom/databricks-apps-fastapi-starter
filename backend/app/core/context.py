"""Request-scoped context shared across layers without threading objects through calls.

The on-behalf-of-user ``WorkspaceClient`` is set by the workspace-client middleware for
the duration of one request. Code that runs inside that request (including LangGraph
tools invoked from the chat stream and threads started with ``asyncio.to_thread``) reads
it from here, so the compiled chat graph can be built once and still act as the user.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

obo_workspace_client: ContextVar[Any | None] = ContextVar(
    "obo_workspace_client", default=None
)
