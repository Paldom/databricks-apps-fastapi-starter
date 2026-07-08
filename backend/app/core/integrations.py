from __future__ import annotations

from collections.abc import Generator
from typing import Any

import httpx
from databricks.sdk import WorkspaceClient
from openai import AsyncOpenAI

from app.core.config import Settings
from app.core.databricks.vector_search import init_vector_index
from app.core.databricks.workspace import get_workspace_client_singleton
from app.core.errors import ConfigurationError, ServiceUnavailableError
from app.core.runtime import AppRuntime


def databricks_integrations_disabled_message() -> str:
    return (
        "Databricks integrations are disabled; set "
        "ENABLE_DATABRICKS_INTEGRATIONS=true to enable them"
    )


def workspace_not_configured_message(detail: str | None = None) -> str:
    base = "Databricks workspace client is not configured"
    return f"{base}: {detail}" if detail else base


def ai_not_configured_message() -> str:
    return "AI integration is not configured; set SERVING_ENDPOINT_NAME"


def vector_not_configured_message() -> str:
    return (
        "Vector Search is not configured; set VECTOR_SEARCH_ENDPOINT_NAME and "
        "VECTOR_SEARCH_INDEX_NAME"
    )


class DatabricksBearerAuth(httpx.Auth):
    """httpx auth hook that injects a fresh Databricks credential per request.

    ``Config.token`` is only set for PAT auth — under the app's OAuth M2M
    identity it is ``None``, and any static token would expire after ~1h.
    ``Config.authenticate()`` returns cached-but-refreshed headers, the same
    mechanism the SDK's own ``serving_endpoints.get_open_ai_client()`` uses.
    """

    def __init__(self, config: Any) -> None:
        self._config = config

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = self._config.authenticate()["Authorization"]
        yield request


def ensure_workspace_client(runtime: AppRuntime, settings: Settings) -> WorkspaceClient:
    if not settings.databricks_integrations_enabled():
        raise ConfigurationError(databricks_integrations_disabled_message())

    if runtime.workspace_client is not None:
        return runtime.workspace_client

    try:
        runtime.workspace_client = get_workspace_client_singleton()
        return runtime.workspace_client
    except Exception as exc:
        if not settings.has_explicit_databricks_auth():
            raise ConfigurationError(
                workspace_not_configured_message(str(exc))
            ) from exc
        raise ServiceUnavailableError(
            f"Databricks workspace client is unavailable: {exc}"
        ) from exc


def ensure_ai_client(runtime: AppRuntime, settings: Settings) -> AsyncOpenAI:
    if not settings.databricks_integrations_enabled():
        raise ConfigurationError(databricks_integrations_disabled_message())

    if runtime.ai_client is not None:
        return runtime.ai_client

    if not settings.has_ai_config():
        raise ConfigurationError(ai_not_configured_message())

    try:
        workspace = ensure_workspace_client(runtime, settings)
    except ConfigurationError as exc:
        raise ConfigurationError(
            f"AI integration requires Databricks workspace configuration: {exc.detail}"
        ) from exc

    try:
        cfg = workspace.config
        timeout = float(settings.openai_timeout_seconds)
        runtime.ai_client = AsyncOpenAI(
            api_key="no-token",  # placeholder; DatabricksBearerAuth injects auth
            base_url=f"{cfg.host}/serving-endpoints",
            timeout=timeout,
            http_client=httpx.AsyncClient(
                auth=DatabricksBearerAuth(cfg), timeout=timeout
            ),
        )
        return runtime.ai_client
    except Exception as exc:
        raise ServiceUnavailableError(f"AI client is unavailable: {exc}") from exc


def ensure_vector_index(runtime: AppRuntime, settings: Settings) -> Any:
    if not settings.databricks_integrations_enabled():
        raise ConfigurationError(databricks_integrations_disabled_message())

    if runtime.vector_index is not None:
        return runtime.vector_index

    if not settings.has_vector_search_config():
        raise ConfigurationError(vector_not_configured_message())

    try:
        runtime.vector_index = init_vector_index(settings)
        return runtime.vector_index
    except Exception as exc:
        if not settings.has_explicit_databricks_auth():
            raise ConfigurationError(f"Vector Search is not configured: {exc}") from exc
        raise ServiceUnavailableError(
            f"Vector Search index is unavailable: {exc}"
        ) from exc
