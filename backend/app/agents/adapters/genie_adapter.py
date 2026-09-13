"""Adapter for Databricks Genie: conversations, bounded polling, query results.

Genie's own conversation and message ids are the handle for follow-ups and for a turn
that is still running when the per-tool deadline expires.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mlflow.types.responses import ResponsesAgentRequest

from app.agents.contracts import AgentInvocationResult
from app.agents.response_utils import last_user_text, text_to_response
from app.core.databricks.genie import GenieClient


TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"}
POLL_SECONDS = 2


def parse_genie_response(rsp: Any) -> dict[str, Any]:
    """Extract structured fields from a Genie SDK message."""
    text_parts: list[str] = []
    sql: str | None = None
    attachments: list[dict[str, Any]] = []
    for attachment in getattr(rsp, "attachments", []) or []:
        record: dict[str, Any] = {"id": getattr(attachment, "attachment_id", None)}
        text_obj = getattr(attachment, "text", None)
        if text_obj is not None:
            content = getattr(text_obj, "content", None) or str(text_obj)
            record["type"] = "text"
            record["text"] = content
            text_parts.append(content)
        query_obj = getattr(attachment, "query", None)
        if query_obj is not None:
            query_str = getattr(query_obj, "query", None) or str(query_obj)
            record["type"] = record.get("type", "query")
            record["query"] = query_str
            sql = sql or query_str
            text_parts.append(f"SQL: {query_str}")
        if len(record) > 1:
            attachments.append(record)
    text = "\n\n".join(part for part in text_parts if part).strip()
    return {
        "text": text or "No Genie response text",
        "sql": sql,
        "attachments": attachments,
        "conversation_id": getattr(rsp, "conversation_id", None),
        "message_id": getattr(rsp, "message_id", None) or getattr(rsp, "id", None),
        "status": _status(rsp),
    }


def _message_id(message: Any) -> str:
    return str(getattr(message, "message_id", None) or getattr(message, "id", ""))


def _status(message: Any) -> str:
    status = getattr(message, "status", None)
    return str(getattr(status, "value", status) or "")


class GenieAdapter:
    """Call Databricks Genie and normalize to ``ResponsesAgentResponse``."""

    source = "genie"

    def __init__(self, workspace_client: Any, space_id: str) -> None:
        self._client = GenieClient(workspace_client, space_id)
        self._space_id = space_id

    async def ask(
        self,
        question: str,
        conversation_id: str | None = None,
        *,
        timeout: float = 45,
    ) -> dict[str, Any]:
        """Ask (or follow up) and poll until the message is terminal or the timeout.

        Returns the parsed message; ``status`` is ``pending`` when the deadline hit.
        """
        if conversation_id:
            message = await self._client.create_message(conversation_id, question)
        else:
            message = await self._client.start_conversation(question)
        try:
            async with asyncio.timeout(timeout):
                while _status(message) not in TERMINAL:
                    await asyncio.sleep(POLL_SECONDS)
                    message = await self._client.get_message(
                        message.conversation_id, _message_id(message)
                    )
        except TimeoutError:
            parsed = parse_genie_response(message)
            parsed["status"] = "pending"
            return parsed
        parsed = parse_genie_response(message)
        parsed["rows"] = await self._rows(message, parsed["attachments"])
        return parsed

    async def status(self, conversation_id: str, message_id: str) -> dict[str, Any]:
        """Current state of a message (for polling a pending turn)."""
        message = await self._client.get_message(conversation_id, message_id)
        parsed = parse_genie_response(message)
        if _status(message) in TERMINAL:
            parsed["rows"] = await self._rows(message, parsed["attachments"])
        else:
            parsed["status"] = "pending"
        return parsed

    async def _rows(self, message: Any, attachments: list[dict[str, Any]]) -> list:
        """Up to MAX_ROWS rows of the first query attachment, as lists of values."""
        attachment = next((a for a in attachments if a.get("query")), None)
        if attachment is None or not attachment.get("id"):
            return []
        return await self._client.query_rows(
            message.conversation_id, _message_id(message), attachment["id"]
        )

    async def invoke(self, request: ResponsesAgentRequest) -> AgentInvocationResult:
        parsed = await self.ask(last_user_text(request))
        normalized = text_to_response(
            parsed["text"],
            custom_outputs={
                "backend": "genie",
                "sql": parsed["sql"],
                "attachments": parsed["attachments"],
                "conversation_id": parsed["conversation_id"],
                "message_id": parsed["message_id"],
                "status": parsed["status"],
                "rows": parsed.get("rows", []),
            },
        )
        return AgentInvocationResult(
            source=self.source,
            response=normalized,
            text=parsed["text"],
            downstream_trace_id=None,  # Genie does not expose MLflow trace ids
            metadata={"space_id": self._space_id},
        )
