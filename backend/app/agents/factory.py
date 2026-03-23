"""Factory for building agent adapters from application settings."""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

from app.core.config import Settings

logger = logging.getLogger(__name__)


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

        return ServingEndpointAdapter(
            ai_client,
            settings.serving_agent_endpoint,
            api_mode=settings.serving_agent_api_mode,
        )

    if backend == "genie":
        if not settings.genie_space_id or workspace_client is None:
            return None
        from app.agents.adapters.genie_adapter import GenieAdapter

        return GenieAdapter(workspace_client, settings.genie_space_id)

    logger.warning("Unknown agent backend: %s", backend)
    return None


def list_available_backends(
    settings: Settings,
    *,
    ai_client: AsyncOpenAI | None = None,
    workspace_client: Any | None = None,
) -> list[str]:
    """Return backend names that are configured and available."""
    backends: list[str] = []
    for name in ("app", "serving_endpoint", "genie"):
        adapter = get_agent_adapter(
            name,
            settings=settings,
            ai_client=ai_client,
            workspace_client=workspace_client,
        )
        if adapter is not None:
            backends.append(name)
    return backends
