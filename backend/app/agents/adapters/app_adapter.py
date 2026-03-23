"""Adapter for a remote Databricks App agent (Responses API)."""

from __future__ import annotations

from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentStreamEvent,
)

from app.agents.contracts import AgentInvocationResult
from app.agents.response_utils import normalize_response
from app.core.mlflow_runtime import extract_trace_id


def _serialize_input(request: ResponsesAgentRequest) -> list[dict[str, Any]]:
    return [
        item.model_dump(exclude_none=True) if hasattr(item, "model_dump") else item
        for item in request.input
    ]


class DatabricksAppAdapter:
    """Call a Databricks App via the Responses API and normalize output."""

    source = "app"

    def __init__(self, client: AsyncOpenAI, app_name: str) -> None:
        self._client = client
        self._app_name = app_name
        self._model = f"apps/{app_name}"

    async def invoke(self, request: ResponsesAgentRequest) -> AgentInvocationResult:
        resp = await self._client.responses.create(
            model=self._model,
            input=_serialize_input(request),
            extra_headers={"x-mlflow-return-trace-id": "true"},
        )

        return AgentInvocationResult(
            source=self.source,
            response=normalize_response(resp),
            text=getattr(resp, "output_text", "") or "",
            downstream_trace_id=extract_trace_id(resp),
            metadata={"model": self._model},
        )

    async def stream(
        self, request: ResponsesAgentRequest
    ) -> AsyncIterator[ResponsesAgentStreamEvent]:
        async for event in await self._client.responses.create(
            model=self._model,
            input=_serialize_input(request),
            stream=True,
            extra_headers={"x-mlflow-return-trace-id": "true"},
        ):
            yield ResponsesAgentStreamEvent(
                **(event.to_dict() if hasattr(event, "to_dict") else dict(event))
            )
