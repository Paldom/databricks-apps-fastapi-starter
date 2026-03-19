from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import app.main as app_main
from app.core.config import settings


def test_workspace_client_middleware_uses_header(monkeypatch):
    created = {}

    class DummyWC:
        def __init__(self, *, host=None, token=None):
            created["host"] = host
            created["token"] = token

    monkeypatch.setattr(settings, "enable_obo", True)
    monkeypatch.setattr(settings, "enable_databricks_integrations", True)
    monkeypatch.setattr(settings, "databricks_host", None)
    monkeypatch.setattr(
        "app.middlewares.workspace_client.WorkspaceClient", DummyWC
    )

    with TestClient(app_main.app) as client:
        client.app.state.runtime.workspace_client = MagicMock(
            config=MagicMock(host="http://h")
        )
        response = client.get(
            "/api/me",
            headers={
                "X-Forwarded-Access-Token": "pat",
                "X-Forwarded-User": "test-user",
            },
        )
    assert response.status_code == 200
    assert created["token"] == "pat"
    assert created["host"] == "http://h"


def test_workspace_client_middleware_ignores_header_when_disabled(monkeypatch):
    called = False

    def dummy_wc(*a, **k):
        nonlocal called
        called = True

    monkeypatch.setattr(settings, "enable_obo", False)
    monkeypatch.setattr(settings, "enable_databricks_integrations", False)
    monkeypatch.setattr(
        "app.middlewares.workspace_client.WorkspaceClient", dummy_wc
    )

    with TestClient(app_main.app) as client:
        client.app.state.runtime.workspace_client = "default"
        response = client.get(
            "/api/me",
            headers={
                "X-Forwarded-Access-Token": "ignored",
                "X-Forwarded-User": "test-user",
            },
        )
    assert response.status_code == 200
    assert not called
