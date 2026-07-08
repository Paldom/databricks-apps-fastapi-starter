"""The AI client must authenticate via per-request Databricks headers.

``Config.token`` is None under OAuth M2M (the deployed app identity), so a
static ``api_key`` breaks in production and a static OAuth token expires
after ~1h. Regression tests for the ``DatabricksBearerAuth`` wiring.
"""

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import httpx
from databricks.sdk import WorkspaceClient

from app.core.config import Settings
from app.core.integrations import DatabricksBearerAuth, ensure_ai_client
from app.core.runtime import AppRuntime


def test_bearer_auth_injects_fresh_header_per_request():
    cfg = MagicMock()
    cfg.authenticate.side_effect = [
        {"Authorization": "Bearer first"},
        {"Authorization": "Bearer second"},
    ]
    auth = DatabricksBearerAuth(cfg)

    for expected in ("Bearer first", "Bearer second"):
        request = httpx.Request("POST", "https://example.test/serving-endpoints")
        flow = auth.auth_flow(request)
        sent = next(flow)
        assert sent.headers["Authorization"] == expected


def test_ensure_ai_client_uses_bearer_auth_not_static_token():
    settings = Settings(
        enable_databricks_integrations=True,
        serving_endpoint_name="chat-endpoint",
    )
    runtime = AppRuntime()
    stub = SimpleNamespace(  # config-only stub; ensure_ai_client reads .config
        config=SimpleNamespace(
            host="https://example.test",
            token=None,  # OAuth M2M: no static token available
            authenticate=lambda: {"Authorization": "Bearer fresh"},
        )
    )
    runtime.workspace_client = cast(WorkspaceClient, stub)

    client = ensure_ai_client(runtime, settings)

    assert str(client.base_url).startswith("https://example.test/serving-endpoints")
    transport_auth = client._client._auth  # underlying httpx.AsyncClient auth
    assert isinstance(transport_auth, DatabricksBearerAuth)
