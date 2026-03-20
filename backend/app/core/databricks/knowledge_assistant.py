from collections.abc import AsyncIterator
from logging import Logger

from httpx import AsyncClient, HTTPStatusError

from app.core.errors import ExternalServiceError
from app.core.observability import get_tracer, safe_attr, tag_exception


_tracer = get_tracer()


class KnowledgeAssistantAdapter:
    """Adapter for Databricks Knowledge Assistant (Agent Bricks) via the Responses API."""

    def __init__(self, client: AsyncClient, logger: Logger):
        self._client = client
        self._logger = logger

    async def ask(self, endpoint_name: str, messages: list[dict]) -> dict:
        """Send messages to the Knowledge Assistant and return the full response."""
        with _tracer.start_as_current_span(
            "dependency.knowledge_assistant.ask",
            attributes={
                "dependency": "knowledge_assistant",
                "operation": "ask",
                "ka.endpoint": safe_attr(endpoint_name),
            },
        ) as span:
            self._logger.info(
                "Querying Knowledge Assistant endpoint %s", endpoint_name
            )
            try:
                resp = await self._client.post(
                    "/serving-endpoints/responses",
                    json={
                        "model": endpoint_name,
                        "input": messages,
                    },
                )
                resp.raise_for_status()
                span.set_attribute("result", "ok")
                return resp.json()
            except HTTPStatusError as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise ExternalServiceError(
                    f"Knowledge Assistant request failed: {exc.response.status_code}",
                    cause=exc,
                ) from exc
            except Exception as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise ExternalServiceError(str(exc), cause=exc) from exc

    async def ask_stream(
        self, endpoint_name: str, messages: list[dict]
    ) -> AsyncIterator[bytes]:
        """Stream the Knowledge Assistant response as SSE chunks."""
        with _tracer.start_as_current_span(
            "dependency.knowledge_assistant.ask_stream",
            attributes={
                "dependency": "knowledge_assistant",
                "operation": "ask_stream",
                "ka.endpoint": safe_attr(endpoint_name),
            },
        ) as span:
            self._logger.info(
                "Streaming Knowledge Assistant endpoint %s", endpoint_name
            )
            try:
                async with self._client.stream(
                    "POST",
                    "/serving-endpoints/responses",
                    json={
                        "model": endpoint_name,
                        "input": messages,
                        "stream": True,
                    },
                ) as resp:
                    if resp.is_error:
                        body = (await resp.aread()).decode("utf-8", errors="ignore")
                        span.set_attribute("result", "error")
                        raise ExternalServiceError(
                            f"Knowledge Assistant stream failed: {resp.status_code} {body}"
                        )
                    span.set_attribute("result", "ok")
                    async for chunk in resp.aiter_bytes():
                        yield chunk
            except ExternalServiceError:
                raise
            except Exception as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise ExternalServiceError(str(exc), cause=exc) from exc
