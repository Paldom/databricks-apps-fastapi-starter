from logging import Logger

from openai import AsyncOpenAI, OpenAIError

from app.core.errors import AiGatewayError


class AiGatewayAdapter:
    def __init__(self, client: AsyncOpenAI, logger: Logger):
        self._client = client
        self._logger = logger

    async def embed(self, model: str, text: str) -> list[float]:
        """Return embedding vector for the given text."""
        self._logger.info("Embedding text using model %s", model)
        try:
            rsp = await self._client.embeddings.create(
                model=model,
                input=text,
                extra_body={"usage_context": {"source": "fastapi-demo"}},
            )
            return rsp.data[0].embedding
        except OpenAIError as exc:
            raise AiGatewayError(str(exc), cause=exc) from exc
