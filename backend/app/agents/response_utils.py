"""Helpers for building and inspecting ``ResponsesAgentResponse`` objects."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse


def normalize_response(resp: Any) -> ResponsesAgentResponse:
    """Convert an OpenAI SDK response object to ``ResponsesAgentResponse``.

    Handles both ``resp.to_dict()`` (OpenAI SDK objects) and plain dicts.
    """
    if isinstance(resp, ResponsesAgentResponse):
        return resp
    if hasattr(resp, "to_dict"):
        return ResponsesAgentResponse(**resp.to_dict())
    if isinstance(resp, dict):
        return ResponsesAgentResponse(**resp)
    return ResponsesAgentResponse(**dict(resp))


def _to_dict(obj: Any) -> dict[str, Any]:
    """Coerce a Pydantic model or dict into a plain dict."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return {}


def text_to_response(
    text: str,
    *,
    custom_outputs: dict[str, Any] | None = None,
) -> ResponsesAgentResponse:
    """Wrap plain text into a canonical ``ResponsesAgentResponse``."""
    return ResponsesAgentResponse.model_validate(
        {
            "output": [
                {
                    "type": "message",
                    "id": f"msg_{uuid4().hex}",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": text,
                            "annotations": [],
                        }
                    ],
                }
            ],
            "custom_outputs": custom_outputs or {},
        }
    )


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
