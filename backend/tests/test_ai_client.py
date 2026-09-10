"""The AI client must be built from the workspace OAuth identity, not a static token."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.core import integrations
from app.core.config import Settings
from app.core.runtime import AppRuntime


class _FakeDatabricksOpenAI:
    """Records constructor kwargs; the real client would authenticate over the network."""

    instances: list["_FakeDatabricksOpenAI"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.base_url = "https://example.invalid/serving-endpoints/"
        self.chat = MagicMock()
        _FakeDatabricksOpenAI.instances.append(self)


def test_ai_client_is_bound_to_the_workspace_identity(monkeypatch):
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)
    fake_module = MagicMock(
        AsyncDatabricksOpenAI=_FakeDatabricksOpenAI,
        DatabricksOpenAI=_FakeDatabricksOpenAI,
    )
    monkeypatch.setitem(__import__("sys").modules, "databricks_openai", fake_module)
    _FakeDatabricksOpenAI.instances.clear()

    workspace = MagicMock()
    workspace.config.token = None  # M2M OAuth: there is no PAT to copy
    runtime = AppRuntime(workspace_client=workspace)
    settings = Settings(
        enable_databricks_integrations=True, openai_timeout_seconds=7, _env_file=None
    )

    client = integrations.ensure_ai_client(runtime, settings)

    async_client, sync_client = _FakeDatabricksOpenAI.instances
    assert async_client.kwargs == {"workspace_client": workspace, "timeout": 7.0}
    assert sync_client.kwargs == {"workspace_client": workspace, "timeout": 7.0}
    assert client.sync_client is sync_client
    assert runtime.ai_client is client  # cached on the runtime
    assert "api_key" not in async_client.kwargs


def test_ai_client_requires_integrations_enabled():
    runtime = AppRuntime()
    settings = Settings(enable_databricks_integrations=False, _env_file=None)
    try:
        integrations.ensure_ai_client(runtime, settings)
    except Exception as exc:  # ConfigurationError -> 503
        assert "ENABLE_DATABRICKS_INTEGRATIONS" in str(exc)
    else:
        raise AssertionError("expected ConfigurationError")
