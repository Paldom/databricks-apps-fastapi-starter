from logging import Logger

from openai import AsyncOpenAI, OpenAIError

from app.core.errors import ExternalServiceError
from app.core.observability import get_tracer, safe_attr, tag_exception


_tracer = get_tracer()


class AiGatewayAdapter:
    def __init__(self, client: AsyncOpenAI, logger: Logger):
        self._client = client
        self._logger = logger

    async def embed(self, model: str, text: str) -> list[float]:
        """Return embedding vector for the given text."""
        with _tracer.start_as_current_span(
            "dependency.ai.embed",
            attributes={
                "dependency": "ai",
                "operation": "embed",
                "ai.model": safe_attr(model),
            },
        ) as span:
            self._logger.info("Embedding text using model %s", model)
            try:
                rsp = await self._client.embeddings.create(
                    model=model,
                    input=text,
                    extra_body={"usage_context": {"source": "fastapi-demo"}},
                )
                span.set_attribute("result", "ok")
                return rsp.data[0].embedding
            except OpenAIError as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise ExternalServiceError(str(exc), cause=exc) from exc
