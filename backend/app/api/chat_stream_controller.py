from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from app.chat.context import ChatContext
from app.core.config import settings
from app.core.deps import get_chat_orchestrator
from app.core.logging import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
_logger = get_logger()


# ── Request schemas ────────────────────────────────────────────────


class ChatStreamMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatStreamRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "messages": [{"role": "user", "content": "Hello, how are you?"}],
            }
        }
    )

    thread_id: str | None = None
    messages: list[ChatStreamMessage]
    run_config: dict[str, Any] | None = None


# ── Streaming event schemas (for OpenAPI documentation) ────────────


class TextDeltaEvent(BaseModel):
    type: Literal["text-delta"]
    delta: str


class ToolCallBeginEvent(BaseModel):
    type: Literal["tool-call-begin"]
    tool_call_id: str
    tool_name: str


class ToolCallDeltaEvent(BaseModel):
    type: Literal["tool-call-delta"]
    tool_call_id: str
    args_delta: str


class DoneEvent(BaseModel):
    type: Literal["done"]
    finish_reason: Literal["stop", "length", "error"]
    trace_id: str | None = None


class ErrorEvent(BaseModel):
    type: Literal["error"]
    message: str
    code: str | None = None
    trace_id: str | None = None


# These are referenced by the custom OpenAPI hook in app/main.py
STREAMING_EVENT_MODELS = [
    TextDeltaEvent,
    ToolCallBeginEvent,
    ToolCallDeltaEvent,
    DoneEvent,
    ErrorEvent,
]


# ── Route ──────────────────────────────────────────────────────────


@router.post(
    "/stream",
    operation_id="chatStream",
    responses={
        200: {
            "content": {
                "application/x-ndjson": {},
            },
        },
    },
)
async def chat_stream(
    body: ChatStreamRequest,
    request: Request,
    orchestrator=Depends(get_chat_orchestrator),
) -> StreamingResponse:
    user = getattr(request.state, "user", None)
    context = ChatContext(
        user_id=getattr(user, "id", None) if user else None,
        user_email=getattr(user, "email", None) if user else None,
    )

    async def event_source():
        messages = [{"role": m.role, "content": m.content} for m in body.messages]
        stream_ok = False
        async for event in orchestrator.stream(
            messages=messages,
            thread_id=body.thread_id,
            context=context,
        ):
            if event.get("type") == "done":
                stream_ok = True
            yield json.dumps(event, ensure_ascii=False) + "\n"

        # Best-effort title generation after the first successful stream
        if (
            stream_ok
            and body.thread_id
            and settings.enable_chat_title_generation
        ):
            _schedule_title_generation(
                request=request,
                thread_id=body.thread_id,
                user_id=context.user_id,
                transcript=messages,
            )

    return StreamingResponse(event_source(), media_type="application/x-ndjson")


# ── Title generation (best-effort, non-blocking) ─────────────────


def _schedule_title_generation(
    request: Request,
    thread_id: str,
    user_id: str | None,
    transcript: list[dict[str, str]],
) -> None:
    """Fire-and-forget title generation after a successful stream."""
    from app.core.config import settings as app_settings
    from app.core.runtime import get_app_runtime

    runtime = get_app_runtime(request.app)
    session_factory = runtime.session_factory
    ai_client = runtime.ai_client
    if session_factory is None or ai_client is None:
        return
    if not user_id:
        return

    model = (
        app_settings.title_model
        or app_settings.supervisor_model
        or app_settings.serving_endpoint_name
        or "databricks-meta-llama-3-1-70b-instruct"
    )

    async def _run() -> None:
        try:
            from app.chat.title.service import ChatTitleService
            from app.repositories.chat_repository import ChatRepository
            from app.services.chat_service import ChatService

            async with session_factory() as session:
                async with session.begin():
                    repo = ChatRepository(session)
                    chat_svc = ChatService(repo, user_id)
                    title_svc = ChatTitleService(
                        ai_client=ai_client,
                        model=model,
                        chat_service=chat_svc,
                    )
                    await title_svc.maybe_generate_title(
                        chat_id=thread_id,
                        current_title=None,
                        transcript=transcript,
                        user_id=user_id,
                    )
        except Exception:
            _logger.debug("Background title generation failed", exc_info=True)

    asyncio.create_task(_run())
