"""Specialist registry — single source of truth for tools and routing prompt.

Each ``SpecialistSpec`` drives both the LangChain tool that gets registered
and the routing instruction that appears in the supervisor system prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings


@dataclass(frozen=True)
class SpecialistSpec:
    key: str
    description: str
    kind: str
    config_key: str | None = None  # Settings field; None = always enabled


SPECIALISTS: list[SpecialistSpec] = [
    SpecialistSpec(
        key="app_agent",
        description=(
            "Query a specialist agent deployed as a Databricks App "
            "for domain-specific tasks."
        ),
        kind="app",
        config_key="app_agent_name",
    ),
    SpecialistSpec(
        key="genie",
        description=(
            "Query Databricks Genie for structured analytics, metrics, "
            "KPIs, trends, counts, or SQL-like questions."
        ),
        kind="genie",
        config_key="genie_space_id",
    ),
    SpecialistSpec(
        key="knowledge_assistant",
        description=(
            "Search indexed documents, manuals, policies, or "
            "volume-backed knowledge via Vector Search."
        ),
        kind="knowledge",
        config_key="ai_gateway_embedding_model",
    ),
    SpecialistSpec(
        key="serving_endpoint",
        description=(
            "Query a model or agent on a Databricks Model Serving endpoint "
            "for specialized inference."
        ),
        kind="serving_endpoint",
        config_key="serving_agent_endpoint",
    ),
]


def get_enabled_specs(settings: Settings) -> list[SpecialistSpec]:
    """Return only the specialists whose backing resources are configured."""
    enabled: list[SpecialistSpec] = []
    for spec in SPECIALISTS:
        if spec.config_key is None:
            enabled.append(spec)
        elif getattr(settings, spec.config_key, None):
            enabled.append(spec)
    return enabled


def build_routing_instructions(specs: list[SpecialistSpec]) -> str:
    """Build the routing section of the supervisor prompt from enabled specs."""
    if not specs:
        return "No specialist tools are available. Answer all questions directly."
    lines = ["Available specialists:"]
    for spec in specs:
        lines.append(f"- Use {spec.key} for: {spec.description}")
    return "\n".join(lines)


_SUPERVISOR_PREAMBLE = """\
You are the chat supervisor for a Databricks application.

Choose the smallest number of tools needed to answer correctly.
If the request is trivial and no tool is needed, answer directly.
When you use tools, synthesize a final answer for the user.
Do not expose internal routing details unless helpful.
"""


def build_supervisor_prompt(specs: list[SpecialistSpec]) -> str:
    """Build the full supervisor system prompt."""
    return _SUPERVISOR_PREAMBLE + "\n" + build_routing_instructions(specs)
