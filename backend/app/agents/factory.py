"""Factory for building agent adapters from application settings."""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

from app.core.config import Settings

logger = logging.getLogger(__name__)

KNOWN_BACKENDS = ("app", "serving_endpoint", "genie")


def get_agent_adapter(
    backend: str,
    *,
    settings: Settings,
    ai_client: AsyncOpenAI | None = None,
    workspace_client: Any | None = None,
) -> Any:
    """Return the adapter for *backend*, or ``None`` if not configured.

    The returned object satisfies the ``AgentAdapter`` protocol.
    """
    if backend == "app":
        if not settings.app_agent_name or ai_client is None:
            return None
        from app.agents.adapters.app_adapter import DatabricksAppAdapter

        return DatabricksAppAdapter(ai_client, settings.app_agent_name)

    if backend == "serving_endpoint":
        if not settings.serving_agent_endpoint or ai_client is None:
            return None
        from app.agents.adapters.serving_adapter import ServingEndpointAdapter

        return ServingEndpointAdapter(ai_client, settings.serving_agent_endpoint)

    if backend == "genie":
        if not settings.genie_space_id or workspace_client is None:
            return None
        from app.agents.adapters.genie_adapter import GenieAdapter

        return GenieAdapter(workspace_client, settings.genie_space_id)

    logger.warning("Unknown agent backend: %s", backend)
    return None


def list_available_backends(settings: Settings) -> list[str]:
    """Return backend names that are configured (by settings alone).

    ``supervisor`` (this app's own LangGraph agent) is always available.
    """
    configured = {
        "app": bool(settings.app_agent_name),
        "serving_endpoint": bool(settings.serving_agent_endpoint),
        "genie": bool(settings.genie_space_id),
    }
    return ["supervisor"] + [name for name in KNOWN_BACKENDS if configured[name]]
