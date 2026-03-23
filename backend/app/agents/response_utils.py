"""Helpers for building and inspecting ``ResponsesAgentResponse`` objects."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from mlflow.types.responses import ResponsesAgentResponse


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
    return ResponsesAgentResponse(
        output=[
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
        custom_outputs=custom_outputs or {},
    )


def response_to_text(response: ResponsesAgentResponse) -> str:
    """Extract the first text block from a ``ResponsesAgentResponse``."""
    for item in response.output or []:
        obj = _to_dict(item)
        for content_block in obj.get("content", []):
            block = _to_dict(content_block)
            if block.get("type") == "output_text" and block.get("text"):
                return block["text"]
    return ""
