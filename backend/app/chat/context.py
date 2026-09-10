"""Per-request context passed through the chat orchestration pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ChatContext:
    """Metadata about the current request, extracted from auth headers."""

    user_id: str | None = None
    user_email: str | None = None
    chat_id: str | None = None
    project_id: str | None = None
    genie_conversation_id: str | None = None

    def configurable(self) -> dict[str, str | None]:
        """What tools may read from the LangGraph run config (never secrets)."""
        return {
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "genie_conversation_id": self.genie_conversation_id,
        }
