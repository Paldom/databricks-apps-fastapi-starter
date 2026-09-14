"""Model Serving agent: a ``ResponsesAgent`` that forwards to a Foundation Model endpoint.

Logged with ``resources=[DatabricksServingEndpoint(...)]`` so the endpoint authenticates
with managed credentials; no secret scope, no client secret in environment variables.
The upstream call uses chat completions (Foundation Model endpoints do not pass the
Responses API through) and the reply is shaped with the ResponsesAgent helpers.
"""

from __future__ import annotations

import os
from typing import Any, Generator

import mlflow
from mlflow.models import set_model
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

mlflow.openai.autolog()

DEFAULT_SYSTEM_PROMPT = "You are a concise assistant. Answer helpfully."
DEFAULT_MODEL = "databricks-claude-sonnet-4-6"


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    return "" if content is None else str(content)


class ChatAgent(ResponsesAgent):
    """Forward the Responses input to the upstream model, keep the client lazy."""

    def __init__(self) -> None:
        self.model = os.getenv("SERVING_AGENT_CHAT_MODEL", DEFAULT_MODEL)
        self.system_prompt = os.getenv(
            "SERVING_AGENT_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT
        )
        self._client: Any = None  # built on first call (no network at load time)

    @property
    def client(self) -> Any:
        if self._client is None:
            from databricks_openai import DatabricksOpenAI

            self._client = DatabricksOpenAI()
        return self._client

    def _messages(self, request: ResponsesAgentRequest) -> list[dict[str, str]]:
        messages = [
            {"role": item.get("role", "user"), "content": _text(item.get("content"))}
            for item in (i.model_dump(exclude_none=True) for i in request.input)
            if item.get("role") in ("system", "user", "assistant")
        ]
        if not any(m["role"] == "system" for m in messages):
            messages.insert(0, {"role": "system", "content": self.system_prompt})
        return messages

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        completion = self.client.chat.completions.create(
            model=self.model, messages=self._messages(request)
        )
        text = completion.choices[0].message.content or ""
        return ResponsesAgentResponse(
            output=[self.create_text_output_item(text=text, id=completion.id)]
        )

    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        stream = self.client.chat.completions.create(
            model=self.model, messages=self._messages(request), stream=True
        )
        item_id = "msg_stream"
        collected: list[str] = []
        for chunk in stream:
            item_id = chunk.id or item_id
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                collected.append(delta)
                yield ResponsesAgentStreamEvent(
                    **self.create_text_delta(delta=delta, item_id=item_id)
                )
        yield ResponsesAgentStreamEvent(
            type="response.output_item.done",
            item=self.create_text_output_item(text="".join(collected), id=item_id),
        )


set_model(ChatAgent())
