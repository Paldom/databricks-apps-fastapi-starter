"""Tool builders for each specialist kind.

Each builder produces a LangChain ``@tool`` from a ``SpecialistSpec``. Tools delegate
to the agent adapters (app, serving, Genie) and to the Vector Search adapter. Failures
raise ``ToolException`` so the graph records an error tool message (the model sees the
error, the client sees ``isError``) instead of an error string posing as an answer.
Every call is bounded by ``Settings.tool_timeout_seconds``; the caller's identity
arrives through the run config (``ChatContext.configurable``), never through tool
arguments.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import ToolException, tool
from openai import AsyncOpenAI

from app.chat.registry import SpecialistSpec
from app.core.config import Settings
from app.core.context import obo_workspace_client, record_turn
from app.core.observability import get_tracer, safe_attr, tag_exception

_tracer = get_tracer()
_logger = logging.getLogger(__name__)

KNOWLEDGE_COLUMNS = [
    "chunk_text",
    "doc_uri",
    "document_title",
    "file_name",
    "chunk_index",
]

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Builder dispatch
# ---------------------------------------------------------------------------


def build_tools(
    specs: list[SpecialistSpec],
    settings: Settings,
    *,
    ai_client: AsyncOpenAI,
    workspace_client: Any | None = None,
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
        built = builder_fn(  # type: ignore[operator]
            spec, settings, ai_client=ai_client, workspace_client=workspace_client
        )
        built.__doc__ = spec.description
        tools.append(built)
        log.info("Registered tool: %s", spec.key)
    return tools


async def _bounded(
    name: str, settings: Settings, call: Callable[[], Awaitable[T]]
) -> T:
    """Run one tool call with a span, a deadline and a ToolException on failure."""
    with _tracer.start_as_current_span(
        f"tool.{name}", attributes={"tool": name}
    ) as span:
        try:
            async with asyncio.timeout(settings.tool_timeout_seconds):
                result = await call()
            span.set_attribute("result", "ok")
            return result
        except TimeoutError as exc:
            tag_exception(span, exc)
            raise ToolException(
                f"{name} did not answer within {settings.tool_timeout_seconds:.0f}s"
            ) from exc
        except ToolException:
            raise
        except Exception as exc:
            tag_exception(span, exc)
            _logger.warning("Tool %s failed", name, exc_info=True)
            raise ToolException(f"{name} failed") from exc  # details stay server-side


def _configurable(config: RunnableConfig | None) -> dict[str, Any]:
    return dict((config or {}).get("configurable") or {})


# ---------------------------------------------------------------------------
# App agent, serving endpoint — Responses-style adapters
# ---------------------------------------------------------------------------


def _build_app_agent_tool(
    spec: SpecialistSpec, settings: Settings, *, ai_client: AsyncOpenAI, **_: Any
) -> Any:
    from app.agents.adapters.app_adapter import DatabricksAppAdapter
    from app.agents.contracts import ResponsesAgentRequest

    adapter = DatabricksAppAdapter(ai_client, settings.app_agent_name or "")

    @tool
    async def app_agent(question: str) -> str:
        """Query a specialist agent deployed as a Databricks App."""

        async def call() -> str:
            request = ResponsesAgentRequest.model_validate(
                {"input": [{"role": "user", "content": question}]}
            )
            return (await adapter.invoke(request)).text

        return await _bounded("app_agent", settings, call)

    return app_agent


def _build_serving_tool(
    spec: SpecialistSpec, settings: Settings, *, ai_client: AsyncOpenAI, **_: Any
) -> Any:
    from app.agents.adapters.serving_adapter import ServingEndpointAdapter
    from app.agents.contracts import ResponsesAgentRequest

    adapter = ServingEndpointAdapter(ai_client, settings.serving_agent_endpoint or "")

    @tool
    async def serving_endpoint(question: str) -> str:
        """Query a Databricks Model Serving endpoint."""

        async def call() -> str:
            request = ResponsesAgentRequest.model_validate(
                {"input": [{"role": "user", "content": question}]}
            )
            return (await adapter.invoke(request)).text

        return await _bounded("serving", settings, call)

    return serving_endpoint


# ---------------------------------------------------------------------------
# Genie — conversation reuse per chat, bounded polling
# ---------------------------------------------------------------------------


def _build_genie_tool(
    spec: SpecialistSpec,
    settings: Settings,
    *,
    workspace_client: Any | None = None,
    **_: Any,
) -> Any:
    from app.agents.adapters.genie_adapter import GenieAdapter

    space_id = settings.genie_space_id or ""
    require_obo = settings.enable_obo is True

    @tool
    async def genie(question: str, config: RunnableConfig) -> str:
        """Query Databricks Genie for data analysis and SQL-based insights."""
        client = obo_workspace_client.get()
        if client is None and require_obo:
            raise ToolException(
                "Genie unavailable: the request carries no user authorization"
            )
        client = client or workspace_client
        if client is None:
            raise ToolException("Genie unavailable: workspace client not configured")
        conversation_id = _configurable(config).get("genie_conversation_id")

        async def call() -> str:
            result = await GenieAdapter(client, space_id).ask(
                question, conversation_id, timeout=settings.tool_timeout_seconds - 5
            )
            if (
                result["conversation_id"]
                and result["conversation_id"] != conversation_id
            ):
                record_turn(genie_conversation_id=result["conversation_id"])
            if result["status"] in ("FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"):
                raise ToolException(f"Genie {result['status'].lower()}")
            return _genie_text(result)

        return await _bounded("genie", settings, call)

    return genie


def _genie_text(result: dict[str, Any]) -> str:
    if result["status"] == "pending":
        return (
            "Genie is still working on this question (conversation "
            f"{result['conversation_id']}, message {result['message_id']}); "
            "ask again in a moment."
        )
    text = result["text"]
    rows = result.get("rows") or []
    if rows:
        text += f"\n\nFirst {len(rows)} result rows:\n" + "\n".join(
            ", ".join(str(v) for v in row) for row in rows[:20]
        )
    return text


# ---------------------------------------------------------------------------
# Knowledge — Knowledge Assistant endpoint or direct AI Search (owner-scoped)
# ---------------------------------------------------------------------------


def _build_knowledge_tool(
    spec: SpecialistSpec,
    settings: Settings,
    *,
    ai_client: AsyncOpenAI,
    workspace_client: Any | None = None,
    **_: Any,
) -> Any:
    if settings.knowledge_assistant_endpoint:
        return _build_ka_endpoint_tool(settings, ai_client=ai_client)
    return _build_direct_vs_tool(settings, workspace_client=workspace_client)


def _build_ka_endpoint_tool(settings: Settings, *, ai_client: AsyncOpenAI) -> Any:
    endpoint = settings.knowledge_assistant_endpoint or ""

    @tool
    async def knowledge_assistant(question: str) -> str:
        """Search the knowledge base for relevant documents."""

        async def call() -> str:
            resp = await ai_client.responses.create(
                model=endpoint, input=[{"role": "user", "content": question}]
            )
            return getattr(resp, "output_text", "") or "No relevant documents found."

        return await _bounded("knowledge", settings, call)

    return knowledge_assistant


def _build_direct_vs_tool(settings: Settings, *, workspace_client: Any | None) -> Any:
    index_name = settings.vector_search_index_name or ""

    @tool
    async def knowledge_assistant(question: str, config: RunnableConfig) -> str:
        """Search the knowledge base for relevant documents."""
        user_id = _configurable(config).get("user_id")
        if not user_id:
            raise ToolException("Knowledge base unavailable: no user in the request")
        if workspace_client is None:
            raise ToolException(
                "Knowledge base unavailable: workspace client not configured"
            )

        async def call() -> str:
            from app.core.databricks.vector_search import VectorSearchAdapter

            hits = await VectorSearchAdapter(
                workspace_client, index_name, _logger
            ).similarity_search(
                KNOWLEDGE_COLUMNS,
                query_text=question,
                filters={"user_id": user_id},  # AI Search has no row ACLs; this is it
                num_results=5,
                timeout=settings.vector_timeout_seconds,
            )
            return _format_knowledge_results(hits) or "No relevant documents found."

        return await _bounded("knowledge", settings, call)

    return knowledge_assistant


def _format_knowledge_results(hits: list[dict[str, Any]]) -> str:
    """Numbered chunks with their source, for the supervisor to cite."""
    parts: list[str] = []
    for i, hit in enumerate(hits, 1):
        text = hit.get("chunk_text") or hit.get("text") or ""
        source = hit.get("doc_uri") or hit.get("source_path") or hit.get("file_name")
        entry = f"[{i}] {text}"
        if source:
            entry += f"\n    Source: {safe_attr(source)}"
        if hit.get("score"):
            entry += f" (score: {hit['score']})"
        parts.append(entry)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_TOOL_BUILDERS = {
    "app": _build_app_agent_tool,
    "genie": _build_genie_tool,
    "knowledge": _build_knowledge_tool,
    "serving_endpoint": _build_serving_tool,
}
