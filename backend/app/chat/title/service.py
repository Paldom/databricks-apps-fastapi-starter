from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from app.chat.title.prompts import TITLE_SYSTEM_PROMPT
from app.core.logging import get_logger
from app.core.observability import get_tracer, tag_exception

logger = get_logger()
_tracer = get_tracer()


class ChatTitleService:
    """Generate concise chat session titles from conversation transcripts."""

    def __init__(
        self,
        ai_client: AsyncOpenAI,
        model: str,
        chat_service: Any | None = None,
    ) -> None:
        self._ai_client = ai_client
        self._model = model
        self._chat_service = chat_service

    async def generate_title(self, transcript: list[dict[str, str]]) -> str | None:
        """Generate a 3-6 word title from the conversation transcript."""
        with _tracer.start_as_current_span("chat.title.generate") as span:
            try:
                # Build a compact transcript summary for the LLM
                summary_parts: list[str] = []
                for msg in transcript[:6]:  # limit to first few messages
                    role = msg.get("role", "user")
                    content = msg.get("content", "")[:200]
                    summary_parts.append(f"{role}: {content}")
                summary = "\n".join(summary_parts)

                rsp = await self._ai_client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": TITLE_SYSTEM_PROMPT},
                        {"role": "user", "content": summary},
                    ],
                    max_tokens=30,
                )
                title = (rsp.choices[0].message.content or "").strip()
                # Truncate to 60 chars
                if len(title) > 60:
                    title = title[:57] + "..."
                span.set_attribute("result", "ok")
                return title or None
            except Exception as exc:
                tag_exception(span, exc)
                logger.warning("Title generation failed: %s", exc)
                return None

    async def maybe_generate_title(
        self,
        *,
        chat_id: str,
        transcript: list[dict[str, str]],
        user_id: str | None = None,
    ) -> str | None:
        """Generate and persist a title if the chat doesn't have one yet.

        Uses set_title_if_empty so an existing non-empty title is never
        overwritten, even if called multiple times concurrently.
        """
        title = await self.generate_title(transcript)
        if not title:
            return None

        if self._chat_service is not None:
            try:
                await self._chat_service.set_title_if_empty(chat_id, title)
                logger.info("Generated title for chat %s: %s", chat_id, title)
            except Exception as exc:
                logger.warning("Failed to persist title for chat %s: %s", chat_id, exc)

        return title
