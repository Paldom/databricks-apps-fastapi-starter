"""Tool builders for each specialist kind.

Each builder produces a LangChain ``@tool`` from a ``SpecialistSpec``.
All builders follow the same pattern: OTel span → try/except → return text.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.chat.registry import SpecialistSpec
from app.core.config import Settings
from app.core.observability import get_tracer, safe_attr, tag_exception

_tracer = get_tracer()
_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Builder dispatch
# ---------------------------------------------------------------------------


def build_tools(
    specs: list[SpecialistSpec],
    settings: Settings,
    *,
    ai_client: AsyncOpenAI,
    workspace_client: Any | None = None,
    vector_index: Any | None = None,
    logger: logging.Logger | None = None,
) -> list:
    """Build LangChain tools from enabled specialist specs."""
    from langchain_core.tools import BaseTool

    log = logger or _logger
    tools: list[BaseTool] = []
    for spec in specs:
        builder_fn = _TOOL_BUILDERS.get(spec.kind)
        if builder_fn is None:
            log.warning("Unknown specialist kind %r for %s", spec.kind, spec.key)
            continue
        tool = builder_fn(  # type: ignore[operator]
            spec, settings,
            ai_client=ai_client,
            workspace_client=workspace_client,
            vector_index=vector_index,
        )
        tools.append(tool)
        log.info("Registered tool: %s", spec.key)
    return tools


# ---------------------------------------------------------------------------
# App agent — remote Databricks App via Responses API
# ---------------------------------------------------------------------------


def _build_app_agent_tool(
    spec: SpecialistSpec,
    settings: Settings,
    *,
    ai_client: AsyncOpenAI,
    **_: Any,
) -> Any:
    from langchain_core.tools import tool

    app_name = settings.app_agent_name
    model = f"apps/{app_name}"

    @tool
    async def app_agent(question: str) -> str:  # noqa: D401
        """Query a specialist agent deployed as a Databricks App."""
        with _tracer.start_as_current_span(
            "tool.app_agent",
            attributes={"tool": "app_agent", "app_name": safe_attr(app_name)},
        ) as span:
            try:
                resp = await ai_client.responses.create(
                    model=model,
                    input=[{"role": "user", "content": question}],
                    extra_headers={"x-mlflow-return-trace-id": "true"},
                )
                text = getattr(resp, "output_text", "") or ""
                # Capture downstream trace ID
                db_out = getattr(resp, "databricks_output", None)
                trace_id = db_out.get("trace", {}).get("trace_id") if isinstance(db_out, dict) else None
                if trace_id:
                    span.set_attribute("downstream.trace_id", str(trace_id))
                span.set_attribute("result", "ok")
                return text
            except Exception as exc:
                tag_exception(span, exc)
                return f"App agent error: {exc}"

    app_agent.__doc__ = spec.description
    return app_agent


# ---------------------------------------------------------------------------
# Genie — Databricks SDK
# ---------------------------------------------------------------------------


def _build_genie_tool(
    spec: SpecialistSpec,
    settings: Settings,
    *,
    workspace_client: Any | None = None,
    **_: Any,
) -> Any:
    from langchain_core.tools import tool

    space_id = settings.genie_space_id or ""

    @tool
    def genie(question: str) -> str:  # noqa: D401
        """Query Databricks Genie for data analysis and SQL-based insights."""
        with _tracer.start_as_current_span(
            "tool.genie",
            attributes={"tool": "genie", "genie.space_id": safe_attr(space_id)},
        ) as span:
            try:
                if workspace_client is None:
                    return "Genie unavailable: workspace client not configured"
                rsp = workspace_client.genie.start_conversation_and_wait(
                    space_id=space_id,
                    content=question,
                )
                span.set_attribute("result", "ok")
                return _format_genie_response(rsp)
            except Exception as exc:
                tag_exception(span, exc)
                return f"Genie error: {exc}"

    genie.__doc__ = spec.description
    return genie


def _format_genie_response(rsp: Any) -> str:
    """Normalize a Genie SDK response to text."""
    parts: list[str] = []
    for att in getattr(rsp, "attachments", []):
        text_content = getattr(att, "text", None)
        if text_content and hasattr(text_content, "content"):
            parts.append(text_content.content)
        query = getattr(att, "query", None)
        if query and hasattr(query, "query"):
            parts.append(f"SQL: {query.query}")
    if parts:
        return "\n\n".join(parts)
    return str(rsp)


# ---------------------------------------------------------------------------
# Knowledge assistant — embed + vector search
# ---------------------------------------------------------------------------


def _build_knowledge_tool(
    spec: SpecialistSpec,
    settings: Settings,
    *,
    ai_client: AsyncOpenAI,
    vector_index: Any | None = None,
    **_: Any,
) -> Any:
    ka_endpoint = settings.knowledge_assistant_endpoint

    # Prefer Knowledge Assistant endpoint when configured (higher-level,
    # includes citations). Fall back to direct embed + vector search.
    if ka_endpoint:
        return _build_ka_endpoint_tool(spec, ka_endpoint, ai_client=ai_client)

    return _build_direct_vs_tool(
        spec, settings, ai_client=ai_client, vector_index=vector_index,
    )


def _build_ka_endpoint_tool(
    spec: SpecialistSpec,
    endpoint: str,
    *,
    ai_client: AsyncOpenAI,
) -> Any:
    """Build a knowledge tool backed by a Knowledge Assistant serving endpoint."""
    from langchain_core.tools import tool

    @tool
    async def knowledge_assistant(question: str) -> str:  # noqa: D401
        """Search the knowledge base for relevant documents."""
        with _tracer.start_as_current_span(
            "tool.knowledge",
            attributes={
                "tool": "knowledge",
                "knowledge.mode": "ka_endpoint",
                "ka.endpoint": safe_attr(endpoint),
            },
        ) as span:
            try:
                resp = await ai_client.responses.create(
                    model=endpoint,
                    input=[{"role": "user", "content": question}],
                )
                text = getattr(resp, "output_text", "") or ""
                span.set_attribute("result", "ok")
                return text if text else "No relevant documents found."
            except Exception as exc:
                tag_exception(span, exc)
                return f"Knowledge assistant error: {exc}"

    knowledge_assistant.__doc__ = spec.description
    return knowledge_assistant


def _build_direct_vs_tool(
    spec: SpecialistSpec,
    settings: Settings,
    *,
    ai_client: AsyncOpenAI,
    vector_index: Any | None = None,
) -> Any:
    """Build a knowledge tool backed by direct embed + vector search."""
    from langchain_core.tools import tool

    embedding_model = settings.ai_gateway_embedding_model or ""
    index_name = settings.vector_search_index_name or ""
    volume_root = settings.knowledge_volume_root or settings.volume_root

    @tool
    async def knowledge_assistant(question: str) -> str:  # noqa: D401
        """Search the knowledge base for relevant documents."""
        with _tracer.start_as_current_span(
            "tool.knowledge",
            attributes={
                "tool": "knowledge",
                "knowledge.mode": "direct_vs",
                "knowledge.index": safe_attr(index_name),
            },
        ) as span:
            try:
                from app.core.databricks.ai_gateway import AiGatewayAdapter
                from app.core.databricks.vector_search import VectorSearchAdapter

                ai_adapter = AiGatewayAdapter(ai_client, _logger)
                query_vector = await ai_adapter.embed(embedding_model, question)

                vs_adapter = VectorSearchAdapter(vector_index, _logger)
                results = await vs_adapter.similarity_search(
                    query_vector=query_vector,
                    columns=["text"],
                    num_results=5,
                    timeout=float(settings.vector_timeout_seconds),
                )

                formatted = _format_knowledge_results(results, volume_root)
                span.set_attribute("result", "ok")
                return formatted if formatted else "No relevant documents found."
            except Exception as exc:
                tag_exception(span, exc)
                return f"Knowledge assistant error: {exc}"

    knowledge_assistant.__doc__ = spec.description
    return knowledge_assistant


def _format_knowledge_results(results: Any, volume_root: str) -> str:
    """Normalize vector search results into a citation-rich string."""
    if results is None:
        return ""
    hits: list[dict[str, Any]] = []
    if isinstance(results, dict):
        data = results.get("result", {})
        if isinstance(data, dict):
            rows = data.get("data_array", [])
            columns = data.get("column_names", [])
            for row in rows:
                hit = dict(zip(columns, row)) if columns else {"text": str(row)}
                hits.append(hit)
        elif isinstance(data, list):
            for item in data:
                hits.append(item if isinstance(item, dict) else {"text": str(item)})
    if not hits:
        return ""
    parts: list[str] = []
    for i, hit in enumerate(hits, 1):
        text = hit.get("text", "")
        score = hit.get("score", "")
        source = hit.get("source_path") or hit.get("metadata", {}).get("source", "")
        entry = f"[{i}] {text}"
        if source:
            entry += f"\n    Source: {source}"
        if score:
            entry += f" (score: {score})"
        parts.append(entry)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Serving endpoint — dual-mode (responses / chat_completions)
# ---------------------------------------------------------------------------


def _build_serving_tool(
    spec: SpecialistSpec,
    settings: Settings,
    *,
    ai_client: AsyncOpenAI,
    **_: Any,
) -> Any:
    from langchain_core.tools import tool

    endpoint = settings.serving_agent_endpoint or ""
    api_mode = settings.serving_agent_api_mode

    @tool
    async def serving_endpoint(question: str) -> str:  # noqa: D401
        """Query a Databricks Model Serving endpoint."""
        with _tracer.start_as_current_span(
            "tool.serving",
            attributes={
                "tool": "serving",
                "serving.endpoint": safe_attr(endpoint),
                "serving.api_mode": safe_attr(api_mode),
            },
        ) as span:
            extra_body: dict[str, Any] = {
                "databricks_options": {"return_trace": True},
            }
            try:
                if api_mode == "responses":
                    resp = await ai_client.responses.create(
                        model=endpoint,
                        input=[{"role": "user", "content": question}],
                        extra_body=extra_body,
                    )
                    text = getattr(resp, "output_text", "") or ""
                    # Capture downstream trace ID
                    metadata = getattr(resp, "metadata", None) or {}
                    trace_id = (
                        metadata.get("trace_id")
                        if isinstance(metadata, dict)
                        else None
                    )
                    if trace_id:
                        span.set_attribute(
                            "downstream.trace_id", str(trace_id)
                        )
                else:
                    completion = await ai_client.chat.completions.create(
                        model=endpoint,
                        messages=[{"role": "user", "content": question}],
                        extra_body=extra_body,
                    )
                    text = completion.choices[0].message.content or ""
                    # Capture downstream trace ID
                    db_out = getattr(completion, "databricks_output", None)
                    trace_id = (
                        db_out.get("trace", {}).get("trace_id")
                        if isinstance(db_out, dict)
                        else None
                    )
                    if trace_id:
                        span.set_attribute(
                            "downstream.trace_id", str(trace_id)
                        )
                span.set_attribute("result", "ok")
                return text
            except Exception as exc:
                tag_exception(span, exc)
                return f"Serving endpoint error: {exc}"

    serving_endpoint.__doc__ = spec.description
    return serving_endpoint


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_TOOL_BUILDERS = {
    "app": _build_app_agent_tool,
    "genie": _build_genie_tool,
    "knowledge": _build_knowledge_tool,
    "serving_endpoint": _build_serving_tool,
}
