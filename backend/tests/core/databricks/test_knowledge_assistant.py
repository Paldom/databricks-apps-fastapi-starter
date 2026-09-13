"""KnowledgeAssistantAdapter calls the Responses API and maps failures."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from app.core.databricks.knowledge_assistant import KnowledgeAssistantAdapter
from app.core.errors import DatabricksAPIError


class _Responses:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("endpoint down")
        if kwargs.get("stream"):

            async def events():
                yield SimpleNamespace(type="response.output_text.delta", delta="hi")

            return events()
        return SimpleNamespace(output_text="answer")


def _adapter(fail: bool = False):
    responses = _Responses(fail)
    client = SimpleNamespace(responses=responses)
    return KnowledgeAssistantAdapter(client, logging.getLogger("test")), responses


@pytest.mark.asyncio
async def test_ask_text_returns_the_output_text():
    adapter, responses = _adapter()
    assert await adapter.ask_text("ka-endpoint", "what?") == "answer"
    assert responses.calls[0]["model"] == "ka-endpoint"
    assert responses.calls[0]["input"] == [{"role": "user", "content": "what?"}]


@pytest.mark.asyncio
async def test_ask_stream_yields_events():
    adapter, _ = _adapter()
    events = [
        e
        async for e in adapter.ask_stream(
            "ka-endpoint", [{"role": "user", "content": "x"}]
        )
    ]
    assert events[0].delta == "hi"


@pytest.mark.asyncio
async def test_failures_map_to_databricks_api_error():
    adapter, _ = _adapter(fail=True)
    with pytest.raises(DatabricksAPIError):
        await adapter.ask("ka-endpoint", [])
