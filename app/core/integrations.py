from __future__ import annotations

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


def _mark_disabled_resources(runtime: AppRuntime) -> None:
    reason = databricks_integrations_disabled_message()
    runtime.disable("workspace_client", reason)
    runtime.disable("ai_client", reason)
    runtime.disable("vector_index", reason)


def initialise_optional_resource_states(runtime: AppRuntime, settings: Settings) -> None:
    if not settings.databricks_integrations_enabled():
        _mark_disabled_resources(runtime)
        return

    runtime.not_configured(
        "workspace_client",
        workspace_not_configured_message(
            "provide Databricks auth or run inside Databricks Apps"
        ),
    )
    if settings.has_ai_config():
        runtime.not_configured("ai_client", "AI client has not been initialized yet")
    else:
        runtime.not_configured("ai_client", ai_not_configured_message())
    if settings.has_vector_search_config():
        runtime.not_configured(
            "vector_index", "Vector Search index has not been initialized yet"
        )
    else:
        runtime.not_configured("vector_index", vector_not_configured_message())


def ensure_workspace_client(runtime: AppRuntime, settings: Settings) -> WorkspaceClient:
    if not settings.databricks_integrations_enabled():
        _mark_disabled_resources(runtime)
        raise ConfigurationError(databricks_integrations_disabled_message())

    if runtime.workspace_client is not None:
        runtime.clear_error("workspace_client")
        return runtime.workspace_client

    if runtime.state_for("workspace_client") == "fail":
        detail = runtime.error_for("workspace_client") or "unknown error"
        raise ServiceUnavailableError(
            f"Databricks workspace client is unavailable: {detail}"
        )

    try:
        runtime.workspace_client = get_workspace_client_singleton()
        runtime.clear_error("workspace_client")
        return runtime.workspace_client
    except Exception as exc:
        detail = str(exc) or exc.__class__.__name__
        if not settings.has_explicit_databricks_auth():
            message = workspace_not_configured_message(detail)
            runtime.not_configured("workspace_client", message)
            raise ConfigurationError(message) from exc
        runtime.remember_error("workspace_client", detail)
        raise ServiceUnavailableError(
            f"Databricks workspace client is unavailable: {detail}"
        ) from exc


def ensure_ai_client(runtime: AppRuntime, settings: Settings) -> AsyncOpenAI:
    if not settings.databricks_integrations_enabled():
        _mark_disabled_resources(runtime)
        raise ConfigurationError(databricks_integrations_disabled_message())

    if runtime.ai_client is not None:
        runtime.clear_error("ai_client")
        return runtime.ai_client

    if runtime.state_for("ai_client") == "fail":
        detail = runtime.error_for("ai_client") or "unknown error"
        raise ServiceUnavailableError(f"AI client is unavailable: {detail}")

    if not settings.has_ai_config():
        message = ai_not_configured_message()
        runtime.not_configured("ai_client", message)
        raise ConfigurationError(message)

    try:
        workspace = ensure_workspace_client(runtime, settings)
    except ConfigurationError as exc:
        message = (
            "AI integration requires Databricks workspace configuration: "
            f"{exc.detail}"
        )
        runtime.not_configured("ai_client", message)
        raise ConfigurationError(message) from exc
    except ServiceUnavailableError as exc:
        runtime.remember_error("ai_client", exc.detail)
        raise ServiceUnavailableError(f"AI client is unavailable: {exc.detail}") from exc

    try:
        cfg = workspace.config
        runtime.ai_client = AsyncOpenAI(
            api_key=cfg.token,
            base_url=f"{cfg.host}/serving-endpoints",
            timeout=float(settings.openai_timeout_seconds),
        )
        runtime.clear_error("ai_client")
        return runtime.ai_client
    except Exception as exc:
        detail = str(exc) or exc.__class__.__name__
        runtime.remember_error("ai_client", detail)
        raise ServiceUnavailableError(f"AI client is unavailable: {detail}") from exc


def ensure_vector_index(runtime: AppRuntime, settings: Settings):
    if not settings.databricks_integrations_enabled():
        _mark_disabled_resources(runtime)
        raise ConfigurationError(databricks_integrations_disabled_message())

    if runtime.vector_index is not None:
        runtime.clear_error("vector_index")
        return runtime.vector_index

    if runtime.state_for("vector_index") == "fail":
        detail = runtime.error_for("vector_index") or "unknown error"
        raise ServiceUnavailableError(
            f"Vector Search index is unavailable: {detail}"
        )

    if not settings.has_vector_search_config():
        message = vector_not_configured_message()
        runtime.not_configured("vector_index", message)
        raise ConfigurationError(message)

    try:
        runtime.vector_index = init_vector_index(settings)
        runtime.clear_error("vector_index")
        return runtime.vector_index
    except Exception as exc:
        detail = str(exc) or exc.__class__.__name__
        if not settings.has_explicit_databricks_auth():
            message = f"Vector Search is not configured: {detail}"
            runtime.not_configured("vector_index", message)
            raise ConfigurationError(message) from exc
        runtime.remember_error("vector_index", detail)
        raise ServiceUnavailableError(
            f"Vector Search index is unavailable: {detail}"
        ) from exc
