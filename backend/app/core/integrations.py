from __future__ import annotations

from databricks.sdk import WorkspaceClient
from openai import AsyncOpenAI

from app.core.config import Settings
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
    return "AI integration is not configured; set ENABLE_DATABRICKS_INTEGRATIONS=true"


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
        # Token-refreshing clients bound to the app's OAuth identity; the async client
        # carries a sync twin for libraries that need one (LangChain).
        from databricks_openai import AsyncDatabricksOpenAI, DatabricksOpenAI

        client = AsyncDatabricksOpenAI(
            workspace_client=workspace,
            timeout=float(settings.openai_timeout_seconds),
        )
        client.sync_client = DatabricksOpenAI(  # type: ignore[attr-defined]
            workspace_client=workspace,
            timeout=float(settings.openai_timeout_seconds),
        )
        runtime.ai_client = client
        return runtime.ai_client
    except Exception as exc:
        raise ServiceUnavailableError(f"AI client is unavailable: {exc}") from exc
