"""Knowledge Assistant (Agent Bricks) client on the Responses API.

The endpoint is a Model Serving endpoint; the token-refreshing ``databricks-openai``
client authenticates, so no static token is involved. Used by the knowledge
specialist (``app.chat.tools``) and the showcase routes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from logging import Logger
from typing import Any, cast

from openai import AsyncOpenAI

from app.core.errors import DatabricksAPIError
from app.core.observability import get_tracer, safe_attr, tag_exception

_tracer = get_tracer()


class KnowledgeAssistantClient:
    def __init__(self, client: AsyncOpenAI, logger: Logger) -> None:
        self._client = client
        self._logger = logger

    async def ask(self, endpoint_name: str, messages: Any) -> Any:
        """One Responses call; returns the SDK response object."""
        with _tracer.start_as_current_span(
            "dependency.knowledge_assistant.ask",
            attributes={
                "dependency": "knowledge_assistant",
                "operation": "ask",
                "ka.endpoint": safe_attr(endpoint_name),
            },
        ) as span:
            self._logger.info("Querying Knowledge Assistant endpoint %s", endpoint_name)
            try:
                response = await self._client.responses.create(
                    model=endpoint_name, input=cast(Any, messages)
                )
            except Exception as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise DatabricksAPIError(
                    f"Knowledge Assistant request failed: {endpoint_name}", cause=exc
                ) from exc
            span.set_attribute("result", "ok")
            return response

    async def ask_text(self, endpoint_name: str, question: str) -> str:
        """The answer text for one question (empty when the endpoint returned none)."""
        response = await self.ask(
            endpoint_name, [{"role": "user", "content": question}]
        )
        return getattr(response, "output_text", "") or ""

    async def ask_stream(self, endpoint_name: str, messages: Any) -> AsyncIterator[Any]:
        """Responses stream events, one per chunk."""
        with _tracer.start_as_current_span(
            "dependency.knowledge_assistant.ask_stream",
            attributes={
                "dependency": "knowledge_assistant",
                "operation": "ask_stream",
                "ka.endpoint": safe_attr(endpoint_name),
            },
        ) as span:
            try:
                stream = await self._client.responses.create(
                    model=endpoint_name, input=cast(Any, messages), stream=True
                )
                async for event in cast(AsyncIterator[Any], stream):
                    yield event
            except Exception as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise DatabricksAPIError(
                    f"Knowledge Assistant stream failed: {endpoint_name}", cause=exc
                ) from exc
            span.set_attribute("result", "ok")
