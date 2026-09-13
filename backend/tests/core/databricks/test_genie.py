"""GenieClient wraps the SDK calls of one space and unwraps waiters."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.databricks.genie import GenieClient
from app.core.errors import DatabricksAPIError


class _Genie:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def start_conversation(self, space_id, question):
        self.calls.append(("start", space_id, question))
        return SimpleNamespace(response=SimpleNamespace(conversation_id="c1", id="m1"))

    def create_message(self, space_id, conversation_id, question):
        self.calls.append(("follow_up", space_id, conversation_id, question))
        return SimpleNamespace(response=SimpleNamespace(conversation_id="c1", id="m2"))

    def get_message(self, space_id, conversation_id, message_id):
        self.calls.append(("get", space_id, conversation_id, message_id))
        return SimpleNamespace(conversation_id=conversation_id, id=message_id)

    def get_message_attachment_query_result(
        self, space_id, conversation_id, message_id, attachment_id
    ):
        if attachment_id == "boom":
            raise RuntimeError("expired")
        rows = [[i] for i in range(150)]
        return SimpleNamespace(
            statement_response=SimpleNamespace(result=SimpleNamespace(data_array=rows))
        )


@pytest.mark.asyncio
async def test_calls_are_scoped_to_the_space_and_unwrapped():
    genie = _Genie()
    client = GenieClient(SimpleNamespace(genie=genie), "space-1")
    first = await client.start_conversation("q")
    follow = await client.create_message(first.conversation_id, "more")
    assert (first.conversation_id, follow.id) == ("c1", "m2")
    assert (await client.get_message("c1", "m2")).id == "m2"
    assert genie.calls[0] == ("start", "space-1", "q")
    assert genie.calls[1] == ("follow_up", "space-1", "c1", "more")


@pytest.mark.asyncio
async def test_query_rows_are_capped_and_failures_are_empty():
    client = GenieClient(SimpleNamespace(genie=_Genie()), "space-1")
    assert len(await client.query_rows("c1", "m1", "a1")) == 100
    assert await client.query_rows("c1", "m1", "boom") == []


@pytest.mark.asyncio
async def test_sdk_errors_become_databricks_api_errors():
    class _Broken:
        def start_conversation(self, *_):
            raise RuntimeError("no space")

    client = GenieClient(SimpleNamespace(genie=_Broken()), "space-1")
    with pytest.raises(DatabricksAPIError):
        await client.start_conversation("q")
