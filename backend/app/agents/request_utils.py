"""Helpers for working with ``ResponsesAgentRequest`` objects."""

from __future__ import annotations

from app.agents.response_utils import _to_dict
from mlflow.types.responses import ResponsesAgentRequest


def last_user_text(request: ResponsesAgentRequest) -> str:
    """Return the text content of the last user message in *request*."""
    for item in reversed(request.input or []):
        obj = _to_dict(item) if not isinstance(item, dict) else item
        if obj.get("role") == "user":
            content = obj.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict) and block.get("text"):
                        parts.append(block["text"])
                return " ".join(parts)
    return ""
