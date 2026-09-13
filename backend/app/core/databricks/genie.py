"""Genie client: the SDK calls behind the Genie specialist, one method per API call.

Authentication is the SDK ``WorkspaceClient`` (the app's OAuth identity, or the user's
under on-behalf-of); conversation state lives in Genie, polling and normalisation in
``app.agents.adapters.genie_adapter``.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.databricks._async_bridge import run_sync
from app.core.errors import DatabricksAPIError
from app.core.observability import get_tracer, safe_attr, tag_exception

_tracer = get_tracer()
logger = logging.getLogger(__name__)

MAX_ROWS = 100


class GenieClient:
    """Conversations, messages and query results of one Genie space."""

    def __init__(self, workspace_client: Any, space_id: str) -> None:
        self._genie = workspace_client.genie
        self._space_id = space_id

    async def start_conversation(self, question: str) -> Any:
        """Open a conversation with the first question; returns the Genie message."""
        waiter = await self._call(
            "start", self._genie.start_conversation, self._space_id, question
        )
        started = waiter.response  # GenieStartConversationResponse, not yet a message
        return started.message or await self.get_message(
            started.conversation_id, started.message_id
        )

    async def create_message(self, conversation_id: str, question: str) -> Any:
        """Follow up in an existing conversation; returns the Genie message."""
        waiter = await self._call(
            "follow_up",
            self._genie.create_message,
            self._space_id,
            conversation_id,
            question,
        )
        return waiter.response

    async def get_message(self, conversation_id: str, message_id: str) -> Any:
        """Current state of a message (Genie answers asynchronously)."""
        return await self._call(
            "get_message",
            self._genie.get_message,
            self._space_id,
            conversation_id,
            message_id,
        )

    async def query_rows(
        self, conversation_id: str, message_id: str, attachment_id: str
    ) -> list[list[Any]]:
        """Up to MAX_ROWS rows of a query attachment; empty when unavailable."""
        try:
            result = await self._call(
                "query_result",
                self._genie.get_message_attachment_query_result,
                self._space_id,
                conversation_id,
                message_id,
                attachment_id,
            )
        except DatabricksAPIError:
            logger.warning("Genie query result unavailable", exc_info=True)
            return []
        data = getattr(getattr(result, "statement_response", None), "result", None)
        return list(getattr(data, "data_array", None) or [])[:MAX_ROWS]

    async def _call(self, operation: str, func: Any, *args: Any) -> Any:
        with _tracer.start_as_current_span(
            f"dependency.genie.{operation}",
            attributes={
                "dependency": "genie",
                "operation": operation,
                "genie.space_id": safe_attr(self._space_id),
            },
        ) as span:
            try:
                result = await run_sync(func, *args, error_cls=DatabricksAPIError)
            except DatabricksAPIError as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise
            span.set_attribute("result", "ok")
            return result
