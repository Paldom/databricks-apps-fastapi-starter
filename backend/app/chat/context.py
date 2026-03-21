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
