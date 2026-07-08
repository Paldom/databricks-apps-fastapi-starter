"""Tool-calling Databricks Model Serving agent using MLflow ResponsesAgent.

This is the **models-from-code file** for the registered model: MLflow executes
it at packaging time and again inside the serving container, and
``mlflow.models.set_model()`` at the bottom registers the agent instance.
Databricks-specific imports are lazy (inside methods) so the file imports
cleanly without credentials — that is also what makes the local smoke test
(``test_agent_smoke.py``) possible.

The agent speaks the MLflow Responses contract on the outside and drives a
chat-completions foundation-model endpoint on the inside:

1. ``predict_stream`` is the real implementation. Each turn it streams the
   upstream LLM and converts the chunks into contract-compliant events via
   ``ResponsesAgent.output_to_responses_items_stream``: every text delta
   carries a stable ``item_id`` and every finished item is closed with a
   ``response.output_item.done`` event carrying the full item.
2. If the LLM answered with ``function_call`` items, the agent executes the
   tools, emits their ``function_call_output`` items as ``output_item.done``
   events, appends everything to the conversation, and loops.
3. ``predict`` is a thin aggregator: it collects the ``output_item.done``
   items from ``predict_stream`` into a single ``ResponsesAgentResponse``.

One tool is offered — ``knowledge_search`` — the DIY RAG pattern from the
app's knowledge module (``backend/app/modules/knowledge_diy``): embed the
question via an AI Gateway embedding endpoint, then query a Vector Search
index directly. It is only registered when both ``VECTOR_SEARCH_INDEX_NAME``
and ``AI_GATEWAY_EMBEDDING_MODEL`` are set; otherwise the agent degrades to a
plain (no-tools) chat agent.

Tracing: ``ResponsesAgent`` auto-traces ``predict``/``predict_stream`` as
AGENT spans, ``mlflow.openai.autolog()`` traces the upstream LLM calls, and
the tool adds manual TOOL/RETRIEVER spans.
"""
from __future__ import annotations

import json
import os
import uuid
from collections.abc import Generator
from typing import Any

import mlflow
from mlflow.entities import SpanType
from mlflow.models import set_model
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

mlflow.set_tracking_uri("databricks")
mlflow.openai.autolog()

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful Databricks chat agent. Answer concisely. "
    "If a knowledge_search tool is available, use it to ground answers "
    "about the knowledge base and cite the sources it returns."
)

# Safety valve so a confused LLM cannot loop tool calls forever.
MAX_TOOL_TURNS = 10

# OpenAI chat-completions tool spec for the knowledge tool. Mirrors the app's
# DIY knowledge specialist (embed + direct Vector Search query).
KNOWLEDGE_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "knowledge_search",
        "description": (
            "Search the knowledge base for documents relevant to the "
            "question. Returns numbered excerpts with source paths."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Natural-language question to search for.",
                }
            },
            "required": ["question"],
        },
    },
}


def format_search_results(results: Any) -> str:
    """Normalize a Vector Search response into a numbered citation list."""
    if not isinstance(results, dict):
        return ""
    data = results.get("result") or {}
    columns = data.get("column_names") or []
    rows = data.get("data_array") or []
    parts: list[str] = []
    for i, row in enumerate(rows, 1):
        hit = dict(zip(columns, row, strict=False)) if columns else {"text": str(row)}
        entry = f"[{i}] {hit.get('text', '')}"
        if source := hit.get("source_path"):
            entry += f"\n    Source: {source}"
        parts.append(entry)
    return "\n\n".join(parts)


class ToolCallingAgent(ResponsesAgent):
    """ResponsesAgent that runs a native tool-calling loop over an FM endpoint."""

    def __init__(self) -> None:
        self.model = os.getenv(
            "SERVING_AGENT_CHAT_MODEL", "databricks-claude-sonnet-4"
        )
        self.system_prompt = os.getenv(
            "SERVING_AGENT_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT
        )
        # Optional knowledge tool config — unset means "no tools".
        self.vector_search_index = os.getenv("VECTOR_SEARCH_INDEX_NAME", "")
        self.embedding_model = os.getenv("AI_GATEWAY_EMBEDDING_MODEL", "")
        # Lazy handles, created on first use so importing this file needs no
        # Databricks credentials (tests inject fakes here).
        self._client: Any = None
        self._vector_index: Any = None

    # ------------------------------------------------------------------
    # Lazy Databricks clients
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            from databricks_openai import DatabricksOpenAI

            self._client = DatabricksOpenAI()
        return self._client

    def _get_vector_index(self) -> Any:
        if self._vector_index is None:
            from databricks.vector_search.client import VectorSearchClient

            self._vector_index = VectorSearchClient().get_index(
                index_name=self.vector_search_index
            )
        return self._vector_index

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @property
    def knowledge_tool_enabled(self) -> bool:
        return bool(self.vector_search_index and self.embedding_model)

    def get_tool_specs(self) -> list[dict[str, Any]]:
        return [KNOWLEDGE_TOOL_SPEC] if self.knowledge_tool_enabled else []

    @mlflow.trace(name="knowledge_search", span_type=SpanType.RETRIEVER)
    def search_knowledge(self, question: str) -> str:
        """Embed the question via AI Gateway, then query Vector Search."""
        embedding = (
            self._get_client()
            .embeddings.create(model=self.embedding_model, input=question)
            .data[0]
            .embedding
        )
        results = self._get_vector_index().similarity_search(
            columns=["text", "source_path"],
            query_vector=embedding,
            num_results=5,
        )
        return format_search_results(results) or "No relevant documents found."

    @mlflow.trace(span_type=SpanType.TOOL)
    def execute_tool(self, name: str, arguments: str) -> str:
        """Run one tool call; errors are returned to the LLM, never raised."""
        try:
            args = json.loads(arguments or "{}")
            if name == "knowledge_search":
                return self.search_knowledge(str(args.get("question", "")))
            return f"Unknown tool: {name}"
        except Exception as exc:
            return f"Tool {name} failed: {exc}"

    # ------------------------------------------------------------------
    # Upstream LLM call (chat completions, streaming)
    # ------------------------------------------------------------------

    def call_llm(self, messages: list[dict[str, Any]]) -> Generator[dict[str, Any], None, None]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": self.prep_msgs_for_cc_llm(messages),
            "stream": True,
        }
        if tool_specs := self.get_tool_specs():
            kwargs["tools"] = tool_specs
        for chunk in self._get_client().chat.completions.create(**kwargs):
            yield chunk.to_dict()

    # ------------------------------------------------------------------
    # ResponsesAgent contract — predict_stream first, predict derived
    # ------------------------------------------------------------------

    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        """The agent loop: stream LLM turns, run tools between them."""
        messages: list[dict[str, Any]] = [
            item.model_dump(exclude_none=True) for item in request.input
        ]
        if not any(m.get("role") == "system" for m in messages):
            messages.insert(0, {"role": "system", "content": self.system_prompt})

        for _ in range(MAX_TOOL_TURNS):
            # Stream one LLM turn. The helper converts chat-completion chunks
            # into Responses events (deltas share the item id; each finished
            # item is closed with output_item.done) and mirrors the finished
            # items into `turn_items` for the next loop iteration.
            turn_items: list[dict[str, Any]] = []
            yield from self.output_to_responses_items_stream(
                self.call_llm(messages), turn_items
            )
            messages.extend(turn_items)

            function_calls = [
                item for item in turn_items if item.get("type") == "function_call"
            ]
            if not function_calls:
                return  # plain text answer — the turn is complete

            for call in function_calls:
                output = self.execute_tool(call["name"], call["arguments"])
                item = self.create_function_call_output_item(call["call_id"], output)
                messages.append(item)
                yield ResponsesAgentStreamEvent(
                    type="response.output_item.done", item=item
                )

        yield ResponsesAgentStreamEvent(
            type="response.output_item.done",
            item=self.create_text_output_item(
                "Stopped: reached the maximum number of tool turns.",
                f"msg-{uuid.uuid4().hex}",
            ),
        )

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        """Non-streaming inference: aggregate the finished stream items."""
        outputs = [
            event.item
            for event in self.predict_stream(request)
            if event.type == "response.output_item.done"
        ]
        return ResponsesAgentResponse(output=outputs, custom_outputs=request.custom_inputs)


set_model(ToolCallingAgent())
