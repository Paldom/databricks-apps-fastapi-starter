from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.core.logging import get_logger

logger = get_logger()


class ChatStreamService:
    def __init__(self, ai_client: AsyncOpenAI, model: str | None = None) -> None:
        self._ai_client = ai_client
        self._model = model or "databricks-meta-llama-3-1-70b-instruct"

    async def stream(
        self,
        messages: list[dict[str, str]],
        thread_id: str | None = None,
        run_config: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict]:
        try:
            response = await self._ai_client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
            )

            async for chunk in response:
                for choice in chunk.choices:
                    delta = choice.delta

                    if delta.content:
                        yield {"type": "text-delta", "delta": delta.content}

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            if tc.function and tc.function.name:
                                yield {
                                    "type": "tool-call-begin",
                                    "tool_call_id": tc.id or "",
                                    "tool_name": tc.function.name,
                                }
                            if tc.function and tc.function.arguments:
                                yield {
                                    "type": "tool-call-delta",
                                    "tool_call_id": tc.id or "",
                                    "args_delta": tc.function.arguments,
                                }

                    if choice.finish_reason:
                        reason = choice.finish_reason
                        mapped = {
                            "stop": "stop",
                            "length": "length",
                        }.get(reason, "stop")
                        yield {"type": "done", "finish_reason": mapped}

        except Exception as exc:
            logger.exception("Chat stream error")
            yield {
                "type": "error",
                "message": str(exc),
                "code": "internal_error",
            }
