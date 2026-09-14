"""Reduce stream events to assistant-ui content parts (the shape the frontend renders)."""

from __future__ import annotations

import json
from typing import Any


class TurnAccumulator:
    def __init__(self) -> None:
        self.parts: list[dict[str, Any]] = []

    def feed(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "text-delta":
            if self.parts and self.parts[-1]["type"] == "text":
                self.parts[-1]["text"] += event["delta"]
            else:
                self.parts.append({"type": "text", "text": event["delta"]})
        elif kind == "tool-call-begin":
            self.parts.append(
                {
                    "type": "tool-call",
                    "toolCallId": event["tool_call_id"],
                    "toolName": event["tool_name"],
                    "argsText": "",
                    "args": {},
                }
            )
        elif kind == "tool-call-delta":
            part = self._tool_call(event["tool_call_id"])
            if part is not None:
                part["argsText"] += event["args_delta"]
                try:
                    part["args"] = json.loads(part["argsText"])
                except ValueError:
                    pass
        elif kind == "tool-result":
            part = self._tool_call(event["tool_call_id"])
            if part is not None:
                part["result"] = event.get("result")
                part["isError"] = bool(event.get("is_error"))

    @property
    def text(self) -> str:
        return "".join(p["text"] for p in self.parts if p["type"] == "text")

    def _tool_call(self, tool_call_id: str) -> dict[str, Any] | None:
        for part in reversed(self.parts):
            if part["type"] == "tool-call" and part["toolCallId"] == tool_call_id:
                return part
        return None
