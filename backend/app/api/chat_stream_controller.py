"""Chat streaming: one turn of the supervisor as NDJSON events.

The chat (``thread_id``) must be owned by the caller. The transcript is server-side: the
turn is built from the stored messages plus the last user message of the request, and
both the user and the assistant message are persisted here. Long turns stay under the
Apps ingress limit through a per-turn deadline and heartbeat events.
"""

from __future__ import annotations

import asyncio
import json
import uuid as _uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from app.chat.context import ChatContext
from app.chat.deps import get_chat_orchestrator
from app.chat.parts import TurnAccumulator
from app.core.config import settings
from app.core.context import log_fields
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.core.mlflow_runtime import get_active_trace_id
from app.models.user_dto import CurrentUser
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])
_logger = get_logger()

HISTORY_LIMIT = 200
HEARTBEAT_SECONDS = 15
_turns = asyncio.Semaphore(settings.max_concurrent_turns)


# ── Request schemas ────────────────────────────────────────────────


class ChatStreamMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatStreamRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "thread_id": "3f9c2a70-1c2e-4d0b-9a6e-1b2c3d4e5f60",
                "messages": [{"role": "user", "content": "Hello, how are you?"}],
            }
        }
    )

    thread_id: str
    messages: list[ChatStreamMessage]


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


class ToolResultEvent(BaseModel):
    type: Literal["tool-result"]
    tool_call_id: str
    result: str
    is_error: bool = False


class HeartbeatEvent(BaseModel):
    type: Literal["heartbeat"]


class DoneEvent(BaseModel):
    type: Literal["done"]
    finish_reason: Literal["stop", "length", "error"]
    thread_id: str | None = None
    trace_id: str | None = None


class ErrorEvent(BaseModel):
    type: Literal["error"]
    message: str
    code: Literal["internal_error", "timeout", "busy"]
    trace_id: str | None = None


STREAMING_EVENT_MODELS: list[type[BaseModel]] = [
    TextDeltaEvent,
    ToolCallBeginEvent,
    ToolCallDeltaEvent,
    ToolResultEvent,
    HeartbeatEvent,
    DoneEvent,
    ErrorEvent,
]


# ── Route ──────────────────────────────────────────────────────────


@router.post(
    "/stream",
    operation_id="chatStream",
    responses={200: {"content": {"application/x-ndjson": {}}}},
)
async def chat_stream(
    body: ChatStreamRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    orchestrator=Depends(get_chat_orchestrator),
) -> StreamingResponse:
    try:
        _uuid.UUID(body.thread_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="thread_id must be a chat id")
    question = next(
        (m.content for m in reversed(body.messages) if m.role == "user" and m.content),
        None,
    )
    if question is None:
        raise HTTPException(status_code=422, detail="messages has no user message")
    # Ownership and history in one short transaction; nothing stays open while streaming.
    async with _chats(request, user.id) as chats:
        chat = await chats.get_owned_chat(body.thread_id)
        if chat is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        history = await chats.recent_transcript(chat["id"], HISTORY_LIMIT)
    transcript = history + [{"role": "user", "content": question}]
    context = ChatContext(
        user_id=user.id,
        user_email=user.email,
        chat_id=chat["id"],
        project_id=chat["project_id"] or None,
        genie_conversation_id=chat["genie_conversation_id"],
    )

    async def event_source() -> AsyncIterator[str]:
        log_fields.set({"session_id": chat["id"], "user_id": user.id})
        if chat["id"] in _active_chats:  # one turn per chat at a time
            yield _line(_error("busy"))
            return
        try:
            await asyncio.wait_for(_turns.acquire(), timeout=2)
        except TimeoutError:
            yield _line(_error("busy"))
            return
        _active_chats.add(chat["id"])
        turn = TurnAccumulator()
        try:
            async with _chats(request, user.id) as chats:
                await chats.add_message(chat["id"], "user", question, [])
            async for event in _with_heartbeat(
                orchestrator.stream(transcript, context),
                deadline=settings.turn_timeout_seconds,
            ):
                turn.feed(event)
                if event.get("type") != "done":
                    yield _line(event)
                    continue
                # Persist before acknowledging: a client that stops at `done` must find the answer.
                started = event.pop("genie_conversation_id", None)
                async with _chats(request, user.id) as chats:
                    await chats.add_message(
                        chat["id"],
                        "assistant",
                        turn.text,
                        turn.parts,
                        event.get("trace_id"),
                    )
                    if started and started != context.genie_conversation_id:
                        await chats.set_genie_conversation(chat["id"], started)
                yield _line(event)
                if settings.enable_chat_title_generation and not chat["title"]:
                    _schedule_title_generation(
                        request, chat["id"], user.id, transcript, turn.text
                    )
        except _TurnError as exc:
            _logger.warning("Chat turn %s (chat=%s)", exc.code, chat["id"])
            yield _line(_error(exc.code, exc.trace_id))
        except Exception:
            _logger.exception("Chat turn failed (chat=%s)", chat["id"])
            yield _line(_error("internal_error"))
        finally:
            _active_chats.discard(chat["id"])
            _turns.release()

    return StreamingResponse(event_source(), media_type="application/x-ndjson")


_active_chats: set[str] = set()


class _TurnError(Exception):
    """A failure inside the producer task, with the trace id captured while it was active."""

    def __init__(self, code: str, trace_id: str | None) -> None:
        super().__init__(code)
        self.code = code
        self.trace_id = trace_id


async def _with_heartbeat(
    events: AsyncIterator[dict[str, Any]], *, deadline: float
) -> AsyncIterator[dict[str, Any]]:
    """Forward events; emit a heartbeat when the producer is quiet; stop at the deadline."""
    queue: asyncio.Queue[Any] = asyncio.Queue()
    stop = object()

    async def produce() -> None:
        try:
            async with asyncio.timeout(deadline):
                async for event in events:
                    await queue.put(event)
        except TimeoutError:
            await queue.put(_TurnError("timeout", get_active_trace_id()))
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            _logger.exception("Chat producer failed")
            await queue.put(_TurnError("internal_error", get_active_trace_id()))
            return
        await queue.put(stop)

    task = asyncio.create_task(produce())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                yield {"type": "heartbeat"}
                continue
            if item is stop:
                return
            if isinstance(item, _TurnError):
                raise item
            yield item
    finally:
        task.cancel()


def _line(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


def _error(code: str, trace_id: str | None = None) -> dict[str, Any]:
    messages = {
        "busy": "The assistant is busy; please retry in a moment.",
        "timeout": "The turn took too long and was stopped.",
        "internal_error": "Something went wrong.",
    }
    return {
        "type": "error",
        "message": messages[code],
        "code": code,
        "trace_id": trace_id,
    }


@asynccontextmanager
async def _chats(request: Request, user_id: str) -> AsyncIterator[ChatService]:
    """A ChatService on its own short transaction (never held across the LLM turn)."""
    from app.core.runtime import get_app_runtime
    from app.repositories.chat_repository import ChatRepository

    factory = get_app_runtime(request.app).session_factory
    if factory is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    async with factory() as session, session.begin():
        yield ChatService(ChatRepository(session), user_id)


# ── Title generation (best-effort, non-blocking) ─────────────────


def _schedule_title_generation(
    request: Request,
    chat_id: str,
    user_id: str,
    transcript: list[dict[str, str]],
    answer: str,
) -> None:
    from app.core.runtime import get_app_runtime

    runtime = get_app_runtime(request.app)
    ai_client = runtime.ai_client
    if runtime.session_factory is None or ai_client is None:
        return
    model = settings.title_model or settings.supervisor_model

    async def _run() -> None:
        try:
            from app.chat.title.service import ChatTitleService

            async with _chats(request, user_id) as chats:
                await ChatTitleService(
                    ai_client=ai_client, model=model, chat_service=chats
                ).maybe_generate_title(
                    chat_id=chat_id,
                    transcript=transcript + [{"role": "assistant", "content": answer}],
                    user_id=user_id,
                )
        except Exception:
            _logger.debug("Background title generation failed", exc_info=True)

    task = asyncio.create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


_background_tasks: set[asyncio.Task[None]] = set()
