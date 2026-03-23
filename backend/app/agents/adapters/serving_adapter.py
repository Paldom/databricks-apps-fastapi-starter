"""Adapter for Databricks Model Serving endpoints.

Defaults to the **Responses API**.  Legacy ``chat_completions`` mode is
kept as a clearly-marked compatibility fallback only.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentStreamEvent,
)

from app.agents.contracts import AgentInvocationResult
from app.agents.response_utils import normalize_response, text_to_response
from app.core.mlflow_runtime import extract_trace_id

_DATABRICKS_OPTIONS = {"databricks_options": {"return_trace": True}}


def _serialize_input(request: ResponsesAgentRequest) -> list[dict[str, Any]]:
    return [
        item.model_dump(exclude_none=True) if hasattr(item, "model_dump") else item
        for item in request.input
    ]


class ServingEndpointAdapter:
    """Invoke a Model Serving endpoint; normalize to ResponsesAgentResponse."""

    source = "serving_endpoint"

    def __init__(
        self,
        client: AsyncOpenAI,
        endpoint: str,
        api_mode: str = "responses",
    ) -> None:
        self._client = client
        self._endpoint = endpoint
        self._api_mode = api_mode

    async def invoke(self, request: ResponsesAgentRequest) -> AgentInvocationResult:
        if self._api_mode == "responses":
            return await self._invoke_responses(request)

        # Legacy compatibility path (chat_completions)
        return await self._invoke_chat_completions(request)

    # ------------------------------------------------------------------
    # Responses API (preferred)
    # ------------------------------------------------------------------

    async def _invoke_responses(
        self, request: ResponsesAgentRequest
    ) -> AgentInvocationResult:
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
            metadata={"endpoint": self._endpoint, "api_mode": self._api_mode},
        )

    # ------------------------------------------------------------------
    # Chat completions (legacy, compatibility only)
    # ------------------------------------------------------------------

    async def _invoke_chat_completions(
        self, request: ResponsesAgentRequest
    ) -> AgentInvocationResult:
        completion = await self._client.chat.completions.create(
            model=self._endpoint,
            messages=_serialize_input(request),
            extra_body=_DATABRICKS_OPTIONS,
        )

        text = completion.choices[0].message.content or ""

        return AgentInvocationResult(
            source=self.source,
            response=text_to_response(
                text, custom_outputs={"legacy_api_mode": "chat_completions"}
            ),
            text=text,
            downstream_trace_id=extract_trace_id(completion),
            metadata={"endpoint": self._endpoint, "api_mode": self._api_mode},
        )

    async def stream(
        self, request: ResponsesAgentRequest
    ) -> AsyncIterator[ResponsesAgentStreamEvent]:
        if self._api_mode != "responses":
            raise NotImplementedError(
                "Streaming only supported in 'responses' mode"
            )

        async for event in await self._client.responses.create(
            model=self._endpoint,
            input=_serialize_input(request),
            stream=True,
            extra_body=_DATABRICKS_OPTIONS,
        ):
            yield ResponsesAgentStreamEvent(
                **(event.to_dict() if hasattr(event, "to_dict") else dict(event))
            )
