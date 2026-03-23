"""Adapter for Databricks Genie — wraps the SDK in the canonical contract.

Preserves structured outputs (SQL, attachments, conversation IDs) in
``custom_outputs`` rather than flattening to plain text.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentStreamEvent,
)

from app.agents.contracts import AgentInvocationResult
from app.agents.request_utils import last_user_text
from app.agents.response_utils import text_to_response


def parse_genie_response(rsp: Any) -> dict[str, Any]:
    """Extract structured fields from a Genie SDK response."""
    text_parts: list[str] = []
    sql: str | None = None
    attachments: list[dict[str, Any]] = []

    for attachment in getattr(rsp, "attachments", []) or []:
        att_record: dict[str, Any] = {}

        # Text content
        text_obj = getattr(attachment, "text", None)
        if text_obj is not None:
            content = getattr(text_obj, "content", None) or str(text_obj)
            att_record["type"] = "text"
            att_record["text"] = content
            text_parts.append(content)

        # SQL query
        query_obj = getattr(attachment, "query", None)
        if query_obj is not None:
            query_str = getattr(query_obj, "query", None) or str(query_obj)
            att_record["type"] = att_record.get("type", "query")
            att_record["query"] = query_str
            if not sql:
                sql = query_str
            text_parts.append(f"SQL: {query_str}")

        if att_record:
            attachments.append(att_record)

    text = "\n\n".join(part for part in text_parts if part).strip()
    if not text:
        text = "No Genie response text"

    return {
        "text": text,
        "sql": sql,
        "attachments": attachments,
        "conversation_id": getattr(rsp, "conversation_id", None),
    }


class GenieAdapter:
    """Call Databricks Genie and normalize to ``ResponsesAgentResponse``."""

    source = "genie"

    def __init__(self, workspace_client: Any, space_id: str) -> None:
        self._workspace_client = workspace_client
        self._space_id = space_id

    async def invoke(self, request: ResponsesAgentRequest) -> AgentInvocationResult:
        question = last_user_text(request)

        rsp = await asyncio.to_thread(
            self._workspace_client.genie.start_conversation_and_wait,
            space_id=self._space_id,
            content=question,
        )

        parsed = parse_genie_response(rsp)

        normalized = text_to_response(
            parsed["text"],
            custom_outputs={
                "backend": "genie",
                "sql": parsed["sql"],
                "attachments": parsed["attachments"],
                "conversation_id": parsed["conversation_id"],
            },
        )

        return AgentInvocationResult(
            source=self.source,
            response=normalized,
            text=parsed["text"],
            downstream_trace_id=None,  # Genie does not provide MLflow trace IDs today
            metadata={"space_id": self._space_id},
        )

    async def stream(
        self, request: ResponsesAgentRequest
    ) -> AsyncIterator[ResponsesAgentStreamEvent]:
        raise NotImplementedError(
            "Genie does not support streaming.  Use invoke() instead."
        )
