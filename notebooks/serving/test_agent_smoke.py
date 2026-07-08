"""Offline smoke test for the tool-calling serving agent.

Drives ``ToolCallingAgent.predict_stream`` and ``predict`` with a fake
Databricks OpenAI client and a fake Vector Search index — no credentials, no
network. Verifies the Responses streaming contract (stable item ids, deltas
closed by ``response.output_item.done``) and the tool-calling loop.

Run from the backend project (its venv has mlflow + openai):

    cd backend && uv run python ../notebooks/serving/test_agent_smoke.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent as agent_module  # notebooks/serving/agent.py
import mlflow
from agent import ToolCallingAgent

# The agent module points tracking at Databricks; keep the test offline.
mlflow.tracing.disable()


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeChunk:
    """Mimics an OpenAI ChatCompletionChunk: only .to_dict() is used."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def to_dict(self) -> dict:
        return self._payload


class FakeChatCompletions:
    """Replays scripted turns; records every create() call for assertions."""

    def __init__(self, turns: list[list[dict]]) -> None:
        self._turns = list(turns)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._turns:
            raise AssertionError("FakeChatCompletions ran out of scripted turns")
        return iter(FakeChunk(payload) for payload in self._turns.pop(0))


class FakeEmbeddings:
    def create(self, *, model: str, input: str):  # "input" is the OpenAI kwarg name
        assert model and input
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])


class FakeClient:
    def __init__(self, turns: list[list[dict]]) -> None:
        self.chat = SimpleNamespace(completions=FakeChatCompletions(turns))
        self.embeddings = FakeEmbeddings()


class FakeVectorIndex:
    def similarity_search(self, *, columns, query_vector, num_results):
        assert "text" in columns and len(query_vector) == 3 and num_results == 5
        return {
            "result": {
                "column_names": ["text", "source_path"],
                "data_array": [
                    ["Vector Search stores embeddings.", "/Volumes/main/docs/vs.pdf"],
                ],
            }
        }


def text_chunks(msg_id: str, *pieces: str) -> list[dict]:
    return [
        {"id": msg_id, "choices": [{"delta": {"role": "assistant", "content": piece}}]}
        for piece in pieces
    ]


def tool_call_chunks(msg_id: str, call_id: str, name: str, *arg_pieces: str) -> list[dict]:
    chunks = [
        {
            "id": msg_id,
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": call_id,
                                "function": {"name": name, "arguments": arg_pieces[0]},
                            }
                        ]
                    }
                }
            ],
        }
    ]
    for piece in arg_pieces[1:]:
        chunks.append(
            {
                "id": msg_id,
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {"index": 0, "function": {"arguments": piece}}
                            ]
                        }
                    }
                ],
            }
        )
    return chunks


def make_agent(turns: list[list[dict]], *, with_tools: bool) -> ToolCallingAgent:
    for var in ("VECTOR_SEARCH_INDEX_NAME", "AI_GATEWAY_EMBEDDING_MODEL"):
        os.environ.pop(var, None)
    if with_tools:
        os.environ["VECTOR_SEARCH_INDEX_NAME"] = "main.default.docs_index"
        os.environ["AI_GATEWAY_EMBEDDING_MODEL"] = "databricks-gte-large-en"
    instance = ToolCallingAgent()
    instance._client = FakeClient(turns)
    instance._vector_index = FakeVectorIndex()
    return instance


REQUEST = {"input": [{"role": "user", "content": "What is Vector Search?"}]}


# ---------------------------------------------------------------------------
# Scenario 1 — no tools configured: plain streaming chat
# ---------------------------------------------------------------------------


def test_no_tools_stream_and_predict() -> None:
    plain_turn = text_chunks("msg-1", "Vector Search ", "is a service.")

    instance = make_agent([list(plain_turn)], with_tools=False)
    assert not instance.knowledge_tool_enabled
    assert instance.get_tool_specs() == []

    events = [e.model_dump() for e in instance.predict_stream(REQUEST)]
    deltas = [e for e in events if e["type"] == "response.output_text.delta"]
    dones = [e for e in events if e["type"] == "response.output_item.done"]

    assert len(deltas) == 2, f"expected 2 text deltas, got {len(deltas)}"
    assert {d["item_id"] for d in deltas} == {"msg-1"}, "deltas must share one item id"
    assert len(dones) == 1 and dones[0]["item"]["type"] == "message"
    done_text = dones[0]["item"]["content"][0]["text"]
    assert done_text == "Vector Search is a service." == "".join(d["delta"] for d in deltas)

    # The upstream call must not advertise tools when none are configured.
    call = instance._client.chat.completions.calls[0]
    assert "tools" not in call
    assert call["messages"][0]["role"] == "system", "system prompt must be injected"

    # predict is a thin aggregator over predict_stream.
    instance = make_agent([list(plain_turn)], with_tools=False)
    response = instance.predict(REQUEST)
    assert [o.type for o in response.output] == ["message"]
    assert response.output[0].content[0]["text"] == "Vector Search is a service."
    print("ok: no-tools streaming + predict aggregation")


# ---------------------------------------------------------------------------
# Scenario 2 — knowledge tool configured: full tool-calling loop
# ---------------------------------------------------------------------------


def test_tool_calling_loop() -> None:
    turns = [
        tool_call_chunks(
            "msg-1", "call-1", "knowledge_search", '{"question": ', '"vector search"}'
        ),
        text_chunks("msg-2", "Vector Search stores embeddings [1]."),
    ]

    instance = make_agent([list(t) for t in turns], with_tools=True)
    assert instance.knowledge_tool_enabled

    events = [e.model_dump() for e in instance.predict_stream(REQUEST)]
    done_types = [
        e["item"]["type"] for e in events if e["type"] == "response.output_item.done"
    ]
    assert done_types == ["function_call", "function_call_output", "message"], done_types

    call_item, output_item, message_item = (
        e["item"] for e in events if e["type"] == "response.output_item.done"
    )
    assert call_item["name"] == "knowledge_search"
    assert call_item["call_id"] == "call-1"
    assert call_item["arguments"] == '{"question": "vector search"}'
    assert output_item["call_id"] == "call-1"
    assert output_item["output"].startswith("[1] Vector Search stores embeddings.")
    assert "/Volumes/main/docs/vs.pdf" in output_item["output"]
    assert message_item["content"][0]["text"] == "Vector Search stores embeddings [1]."

    # First LLM call advertises the tool; second carries the tool result back.
    first, second = instance._client.chat.completions.calls
    assert first["tools"][0]["function"]["name"] == "knowledge_search"
    tool_msgs = [m for m in second["messages"] if m.get("role") == "tool"]
    assert len(tool_msgs) == 1 and tool_msgs[0]["tool_call_id"] == "call-1"

    # predict aggregates the whole loop into one response.
    instance = make_agent([list(t) for t in turns], with_tools=True)
    response = instance.predict(REQUEST)
    assert [o.type for o in response.output] == [
        "function_call",
        "function_call_output",
        "message",
    ]
    print("ok: tool-calling loop streaming + predict aggregation")


# ---------------------------------------------------------------------------
# Scenario 3 — tool errors degrade to a message for the LLM, never raise
# ---------------------------------------------------------------------------


def test_tool_error_is_returned_not_raised() -> None:
    instance = make_agent([], with_tools=True)
    result = instance.execute_tool("knowledge_search", "{not json")
    assert result.startswith("Tool knowledge_search failed:")
    result = instance.execute_tool("nonexistent_tool", "{}")
    assert result == "Unknown tool: nonexistent_tool"
    print("ok: tool errors degrade gracefully")


if __name__ == "__main__":
    # set_model() at import time registered a module-level instance; the test
    # drives fresh instances with fakes injected instead.
    assert isinstance(agent_module, object)
    test_no_tools_stream_and_predict()
    test_tool_calling_loop()
    test_tool_error_is_returned_not_raised()
    print("ALL SMOKE TESTS PASSED")
