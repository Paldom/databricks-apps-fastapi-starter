"""Chat orchestrator: runs one turn of the LangGraph supervisor and translates its events.

The transcript comes from the database on every turn (the backend is the only writer of
messages), so the graph runs without a checkpointer. Per-turn identity travels in the run
config's ``configurable`` map, where tools read it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from logging import Logger
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.chat.context import ChatContext
from app.core.context import record_turn
from app.core.mlflow_runtime import (
    get_active_trace_id,
    root_span,
    stamp_span,
    update_trace_context,
)
from app.core.observability import get_tracer, safe_attr

_tracer = get_tracer()


def convert_messages(
    messages: list[dict[str, Any]],
) -> list[HumanMessage | SystemMessage | AIMessage]:
    out: list[HumanMessage | SystemMessage | AIMessage] = []
    for msg in messages:
        role, content = msg.get("role", "user"), msg.get("content", "")
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out


class ChatOrchestrator:
    def __init__(self, agent: Any, logger: Logger) -> None:
        self._agent = agent
        self._logger = logger

    async def stream(
        self, messages: list[dict[str, Any]], context: ChatContext
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield NDJSON events for one turn; ends with ``done``. Errors propagate."""
        with (
            _tracer.start_as_current_span(
                "chat.orchestrator.stream",
                attributes={"chat.id": safe_attr(context.chat_id)},
            ),
            root_span("chat.turn") as span,
        ):
            _attach_trace_metadata(context)
            record_turn(trace_id=get_active_trace_id())
            stamp_span(
                span, inputs={"question": messages[-1]["content"] if messages else ""}
            )
            state: dict[str, Any] = {}
            answer: list[str] = []
            try:
                async for event in self._agent.astream_events(
                    input={"messages": convert_messages(messages)},
                    config={"configurable": context.configurable()},
                    version="v2",
                ):
                    for out in _translate_event(event, state):
                        if out["type"] == "text-delta":
                            answer.append(out["delta"])
                        yield out
                yield {
                    "type": "done",
                    "finish_reason": "stop",
                    "thread_id": context.chat_id,
                    "trace_id": get_active_trace_id(),
                }
            finally:
                stamp_span(
                    span,
                    outputs={"answer": "".join(answer)},
                    attributes=_turn_attributes(context, state.get("usage", {})),
                )

    async def invoke(
        self, messages: list[dict[str, Any]], context: ChatContext
    ) -> tuple[str, str | None]:
        """Run one turn without streaming; returns (answer text, MLflow trace id)."""
        with (
            _tracer.start_as_current_span(
                "chat.orchestrator.invoke",
                attributes={"chat.id": safe_attr(context.chat_id)},
            ),
            root_span("chat.turn") as span,
        ):
            _attach_trace_metadata(context)
            record_turn(trace_id=get_active_trace_id())
            stamp_span(
                span, inputs={"question": messages[-1]["content"] if messages else ""}
            )
            usage: dict[str, int] = {}
            answer = ""
            try:
                result = await self._agent.ainvoke(
                    {"messages": convert_messages(messages)},
                    config={"configurable": context.configurable()},
                )
                for message in result["messages"]:
                    _add_usage(usage, getattr(message, "usage_metadata", None))
                answer = _answer_text(result["messages"])
                return answer, get_active_trace_id()
            finally:
                stamp_span(
                    span,
                    outputs={"answer": answer},
                    attributes=_turn_attributes(context, usage),
                )


def _turn_attributes(context: ChatContext, usage: dict[str, int]) -> dict[str, Any]:
    return {
        "user.id": context.user_id,
        "session.id": context.chat_id,
        "llm.input_tokens": usage.get("input_tokens"),
        "llm.output_tokens": usage.get("output_tokens"),
    }


def _add_usage(usage: dict[str, int], metadata: Any) -> None:
    """Accumulate LangChain ``usage_metadata`` (per model call) into the turn total."""
    if not metadata:
        return
    for key in ("input_tokens", "output_tokens"):
        value = (
            metadata.get(key)
            if isinstance(metadata, dict)
            else getattr(metadata, key, None)
        )
        if isinstance(value, int):
            usage[key] = usage.get(key, 0) + value


def _answer_text(messages: list[Any]) -> str:
    """Text of the last assistant message that has any (tool turns come between)."""
    for message in reversed(messages):
        if getattr(message, "type", None) != "ai":
            continue
        content = message.content
        if isinstance(content, str):
            if content:
                return content
            continue
        text = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
        if text:
            return text
    return ""


# ---------------------------------------------------------------------------
# Event translation (LangGraph v2 -> NDJSON)
# ---------------------------------------------------------------------------


def _translate_event(
    event: dict[str, Any], state: dict[str, Any]
) -> list[dict[str, Any]]:
    """One LangGraph event -> zero or more NDJSON events.

    ``state`` lives for one turn: ``ids`` maps a chunk index to its tool call id within
    the current model call (only the first chunk of a tool call carries the id), and
    ``begun`` remembers which tool calls were announced.
    """
    ids: dict[int, str] = state.setdefault("ids", {})
    begun: set[str] = state.setdefault("begun", set())
    kind = event.get("event")
    data = event.get("data", {})
    node = event.get("metadata", {}).get("langgraph_node")

    if kind == "on_chat_model_start":
        ids.clear()
        return []

    if kind == "on_chain_end" and event.get("name") == "tools":
        return [
            {
                "type": "tool-result",
                "tool_call_id": message.tool_call_id,
                "result": _text(message.content),
                "is_error": getattr(message, "status", None) == "error",
            }
            for message in (data.get("output") or {}).get("messages", [])
            if getattr(message, "type", None) == "tool"
        ]

    if kind != "on_chat_model_stream" or node not in (None, "agent", "supervisor"):
        return []
    chunk = data.get("chunk")
    if chunk is None:
        return []

    _add_usage(state.setdefault("usage", {}), getattr(chunk, "usage_metadata", None))
    out: list[dict[str, Any]] = []
    text = _text(getattr(chunk, "content", None))
    if text:
        out.append({"type": "text-delta", "delta": text})
    for tc in getattr(chunk, "tool_call_chunks", None) or []:
        index = tc.get("index")
        tc_id = tc.get("id")
        if tc_id and index is not None:
            ids[index] = tc_id
        tc_id = tc_id or (ids.get(index) if index is not None else None)
        if not tc_id:
            continue
        if tc.get("name") and tc_id not in begun:
            begun.add(tc_id)
            out.append(
                {
                    "type": "tool-call-begin",
                    "tool_call_id": tc_id,
                    "tool_name": tc["name"],
                }
            )
        if tc.get("args"):
            out.append(
                {
                    "type": "tool-call-delta",
                    "tool_call_id": tc_id,
                    "args_delta": tc["args"],
                }
            )
    return out


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return "" if content is None else str(content)


def _attach_trace_metadata(context: ChatContext) -> None:
    update_trace_context(
        session_id=context.chat_id,
        user_id=context.user_id,
        chat_id=context.chat_id,
    )
