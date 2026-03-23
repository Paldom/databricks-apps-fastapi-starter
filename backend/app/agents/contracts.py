"""Canonical internal agent contract based on MLflow Responses semantics.

Every backend adapter returns an ``AgentInvocationResult`` wrapping a
``ResponsesAgentResponse``.  The orchestration layer never sees raw
backend-specific shapes.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

# Re-export so callers only need to import from contracts
__all__ = [
    "ResponsesAgentRequest",
    "ResponsesAgentResponse",
    "ResponsesAgentStreamEvent",
    "AgentInvocationResult",
    "AgentAdapter",
]


class AgentInvocationResult(BaseModel):
    """Unified result returned by every adapter."""

    source: str
    response: ResponsesAgentResponse
    text: str = ""
    downstream_trace_id: str | None = None
    downstream_experiment_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class AgentAdapter(Protocol):
    """Protocol every backend adapter must satisfy."""

    source: str

    async def invoke(self, request: ResponsesAgentRequest) -> AgentInvocationResult: ...

    async def stream(
        self, request: ResponsesAgentRequest
    ) -> AsyncIterator[ResponsesAgentStreamEvent]: ...
