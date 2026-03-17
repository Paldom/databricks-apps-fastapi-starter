from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from app.core.deps import get_chat_stream_service
from app.services.chat_stream_service import ChatStreamService

router = APIRouter(prefix="/chat", tags=["chat"])


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


class ErrorEvent(BaseModel):
    type: Literal["error"]
    message: str
    code: str | None = None


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
    service: ChatStreamService = Depends(get_chat_stream_service),
) -> StreamingResponse:
    async def event_source():
        messages = [{"role": m.role, "content": m.content} for m in body.messages]
        async for event in service.stream(
            messages=messages,
            thread_id=body.thread_id,
            run_config=body.run_config,
        ):
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(event_source(), media_type="application/x-ndjson")
