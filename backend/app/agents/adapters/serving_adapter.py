"""Adapter for Databricks Model Serving endpoints.

Speaks the Responses API only.
"""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from mlflow.types.responses import ResponsesAgentRequest

from app.agents.contracts import AgentInvocationResult
from app.agents.response_utils import normalize_response
from app.core.mlflow_runtime import extract_trace_id

_DATABRICKS_OPTIONS = {"databricks_options": {"return_trace": True}}


def _serialize_input(request: ResponsesAgentRequest) -> list[Any]:
    return [item.model_dump(exclude_none=True) for item in request.input]


class ServingEndpointAdapter:
    """Invoke a Model Serving endpoint; normalize to ResponsesAgentResponse."""

    source = "serving_endpoint"

    def __init__(self, client: AsyncOpenAI, endpoint: str) -> None:
        self._client = client
        self._endpoint = endpoint

    async def invoke(self, request: ResponsesAgentRequest) -> AgentInvocationResult:
        resp = await self._client.responses.create(
            model=self._endpoint,
            input=_serialize_input(request),
            extra_body=_DATABRICKS_OPTIONS,
        )

        return AgentInvocationResult(
            source=self.source,
            response=normalize_response(resp),
            text=getattr(resp, "output_text", "") or "",
            downstream_trace_id=extract_trace_id(resp),
            metadata={"endpoint": self._endpoint},
        )
