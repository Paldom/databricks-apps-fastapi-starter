"""Chat orchestrator — the single entry point for chat streaming.

Combines agent execution, memory bootstrapping, event translation,
and MLflow trace correlation into one request-scoped object.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from logging import Logger
from typing import Any

from app.chat.context import ChatContext
from app.chat.memory import build_graph_input
from app.core.mlflow_runtime import get_active_trace_id, update_trace_context
from app.core.observability import get_tracer, safe_attr, tag_exception

_tracer = get_tracer()


class ChatOrchestrator:
    """Stream chat responses from a LangGraph agent with short-term memory."""

    def __init__(
        self,
        agent: Any,
        checkpointer: Any,
        logger: Logger,
    ) -> None:
        self._agent = agent
        self._checkpointer = checkpointer
        self._logger = logger

    async def stream(
        self,
        messages: list[dict[str, Any]],
        thread_id: str | None = None,
        context: ChatContext | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        thread_id = thread_id or str(uuid.uuid4())

        with _tracer.start_as_current_span(
            "chat.orchestrator.stream",
            attributes={
                "chat.thread_id": safe_attr(thread_id),
            },
        ) as span:
            try:
                _attach_trace_metadata(thread_id, context)

                input_state = await build_graph_input(
                    messages, thread_id, self._checkpointer,
                )
                config = {"configurable": {"thread_id": thread_id}}

                seen_tools: set[str] = set()
                async for event in self._agent.astream_events(
                    input=input_state, config=config, version="v2",
                ):
                    for ndjson_event in _translate_event(event, seen_tools):
                        yield ndjson_event

                done: dict[str, Any] = {"type": "done", "finish_reason": "stop"}
                trace_id = get_active_trace_id()
                if trace_id:
                    done["trace_id"] = trace_id
                yield done

                span.set_attribute("result", "ok")

            except Exception as exc:
                tag_exception(span, exc)
                self._logger.exception(
                    "Chat orchestrator error (thread=%s)", thread_id
                )
                error: dict[str, Any] = {
                    "type": "error",
                    "message": str(exc),
                    "code": "internal_error",
                }
                trace_id = get_active_trace_id()
                if trace_id:
                    error["trace_id"] = trace_id
                yield error


# ---------------------------------------------------------------------------
# Event translation (LangGraph v2 → NDJSON)
# ---------------------------------------------------------------------------


def _translate_event(
    event: dict[str, Any], seen_tools: set[str]
) -> list[dict[str, Any]]:
    """Convert a single LangGraph v2 event into zero or more NDJSON events."""
    out: list[dict[str, Any]] = []
    event_type = event.get("event")
    data = event.get("data", {})
    metadata = event.get("metadata", {})

    # Only surface events from the agent node
    node = metadata.get("langgraph_node")
    if node is not None and node not in ("agent", "supervisor"):
        return out

    if event_type != "on_chat_model_stream":
        return out

    chunk = data.get("chunk")
    if chunk is None:
        return out

    content = getattr(chunk, "content", None)
    if content:
        out.append({"type": "text-delta", "delta": content})

    tool_calls = getattr(chunk, "tool_call_chunks", None)
    if tool_calls:
        for tc in tool_calls:
            tc_id = str(tc.get("id") or tc.get("index", ""))
            name = tc.get("name")
            args = tc.get("args")
            if name and tc_id not in seen_tools:
                seen_tools.add(tc_id)
                out.append({
                    "type": "tool-call-begin",
                    "tool_call_id": tc_id,
                    "tool_name": name,
                })
            if args:
                out.append({
                    "type": "tool-call-delta",
                    "tool_call_id": tc_id,
                    "args_delta": args,
                })

    return out


# ---------------------------------------------------------------------------
# MLflow trace helpers (best-effort, via mlflow_runtime)
# ---------------------------------------------------------------------------


def _attach_trace_metadata(
    thread_id: str | None, context: ChatContext | None
) -> None:
    update_trace_context(
        session_id=thread_id,
        user_id=context.user_id if context else None,
        chat_id=context.chat_id if context else None,
    )
