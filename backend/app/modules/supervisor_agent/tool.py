"""Chat tool: delegate to a Databricks-hosted multi-agent supervisor.

The endpoint can be an Agent Bricks Multi-Agent Supervisor (created in the
Agent Bricks UI) or any ``langgraph_supervisor``-style agent on Model
Serving — both speak the Responses API, so the call reuses
``ServingEndpointAdapter`` unchanged.
"""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from app.chat.registry import SpecialistSpec
from app.core.config import Settings
from app.core.observability import get_tracer, safe_attr, tag_exception

_tracer = get_tracer()


def build_mas_tool(
    spec: SpecialistSpec,
    settings: Settings,
    *,
    ai_client: AsyncOpenAI,
    **_: Any,
) -> Any:
    """Build the multi-agent supervisor tool (Responses API forward)."""
    from langchain_core.tools import tool

    from app.agents.adapters.serving_adapter import ServingEndpointAdapter
    from app.agents.contracts import ResponsesAgentRequest

    # Settings.mas_endpoint (env MAS_ENDPOINT); getattr keeps the module
    # importable until the field is wired into app/core/config.py.
    endpoint: str = settings.mas_endpoint or ""
    adapter = ServingEndpointAdapter(ai_client, endpoint)

    @tool
    async def multi_agent_supervisor(question: str) -> str:
        """Delegate a question to a hosted multi-agent supervisor."""
        with _tracer.start_as_current_span(
            "tool.multi_agent_supervisor",
            attributes={
                "tool": "multi_agent_supervisor",
                "mas.endpoint": safe_attr(endpoint),
            },
        ) as span:
            try:
                request = ResponsesAgentRequest(
                    input=[{"role": "user", "content": question}],
                )
                result = await adapter.invoke(request)
                if result.downstream_trace_id:
                    span.set_attribute(
                        "downstream.trace_id", result.downstream_trace_id
                    )
                span.set_attribute("result", "ok")
                return result.text
            except Exception as exc:
                tag_exception(span, exc)
                return f"Multi-agent supervisor error: {exc}"

    multi_agent_supervisor.__doc__ = spec.description
    return multi_agent_supervisor
