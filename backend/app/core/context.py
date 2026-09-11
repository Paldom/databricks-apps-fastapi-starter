"""Request-scoped context shared across layers without threading objects through calls.

The on-behalf-of-user ``WorkspaceClient`` is set by the workspace-client middleware for
the duration of one request. Code that runs inside that request (including LangGraph
tools invoked from the chat stream and threads started with ``asyncio.to_thread``) reads
it from here, so the compiled chat graph can be built once and still act as the user.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

log_fields: ContextVar[dict[str, str]] = ContextVar("log_fields", default={})
# session_id/user_id of the running chat turn, added to every log line by the logging filter

turn_state: ContextVar[dict[str, Any] | None] = ContextVar("turn_state", default=None)
# One dict per chat turn (``trace_id``, ``genie_conversation_id``). LangGraph runs tools in
# their own tasks, so a ContextVar *set* there never reaches the caller; mutating the dict
# the controller created does.


def new_turn_state() -> dict[str, Any]:
    state: dict[str, Any] = {}
    turn_state.set(state)
    return state


def record_turn(**fields: Any) -> None:
    state = turn_state.get()
    if state is not None:
        state.update(fields)


obo_workspace_client: ContextVar[Any | None] = ContextVar(
    "obo_workspace_client", default=None
)
