"""Minimal Databricks Model Serving chat agent using ResponsesAgent.

Calls a Databricks AI Gateway / Foundation Model endpoint via DatabricksOpenAI.
Deployed on custom CPU Model Serving and queried through the Responses API.
"""
from __future__ import annotations

import os
from typing import Generator

import mlflow
from databricks_openai import DatabricksOpenAI
from mlflow.entities import SpanType
from mlflow.models import set_model
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

mlflow.set_tracking_uri("databricks")
mlflow.openai.autolog()

DEFAULT_SYSTEM_PROMPT = (
    "You are a minimal Databricks chat agent. "
    "Answer helpfully and concisely."
)


class ChatAgent(ResponsesAgent):
    """Minimal ResponsesAgent that forwards to an upstream LLM."""

    def __init__(self) -> None:
        self.model = os.getenv(
            "SERVING_AGENT_CHAT_MODEL", "databricks-claude-sonnet-4"
        )
        self.system_prompt = os.getenv(
            "SERVING_AGENT_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT
        )
        self.client = DatabricksOpenAI()

    def _build_input(self, request: ResponsesAgentRequest) -> list[dict]:
        items = [item.model_dump(exclude_none=True) for item in request.input]
        if not any(item.get("role") == "system" for item in items):
            items = [
                {"role": "system", "content": self.system_prompt},
                *items,
            ]
        return items

    def _payload(self, request: ResponsesAgentRequest) -> dict:
        return {
            "model": self.model,
            "input": self._build_input(request),
        }

    def _call_gateway(
        self, request: ResponsesAgentRequest, *, stream: bool = False
    ):
        return self.client.responses.create(
            **self._payload(request), stream=stream
        )

    @mlflow.trace(name="chat_agent.predict", span_type=SpanType.AGENT)
    def predict(
        self, request: ResponsesAgentRequest
    ) -> ResponsesAgentResponse:
        payload = self._payload(request)
        with mlflow.start_span(
            name="ai_gateway", span_type=SpanType.LLM
        ) as span:
            span.set_inputs(payload)
            response = self._call_gateway(request)
            span.set_outputs(
                {"output_text": getattr(response, "output_text", "")}
            )
        return ResponsesAgentResponse(**response.to_dict())

    @mlflow.trace(
        name="chat_agent.predict_stream", span_type=SpanType.AGENT
    )
    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        payload = self._payload(request)
        with mlflow.start_span(
            name="ai_gateway", span_type=SpanType.LLM
        ) as span:
            span.set_inputs(payload)
            for event in self._call_gateway(request, stream=True):
                yield ResponsesAgentStreamEvent(**event.to_dict())
            span.set_outputs({"status": "completed"})


set_model(ChatAgent())
