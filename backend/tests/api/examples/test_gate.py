"""Showcase routes are gated by ENABLE_EXAMPLES and always require identity."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as app_main
from app.core.config import Settings, settings
from app.core.deps import get_settings

AUTH = {"X-Forwarded-User": "test-user"}


def _api_app():
    for route in app_main.app.routes:
        if getattr(route, "path", None) == "/api":
            return route.app
    raise AssertionError("Mounted /api app not found")


def test_examples_disabled_by_default():
    with TestClient(app_main.app, headers=AUTH) as client:
        response = client.post("/api/examples/embed", json={"title": "x"})
    assert response.status_code == 404
    assert "ENABLE_EXAMPLES" in response.json()["detail"]


def test_bound_secret_is_reported_without_its_value(monkeypatch):
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: Settings(
        enable_examples=True,
        example_secret="s3cr3t-value",  # pragma: allowlist secret (test fixture)
        _env_file=None,
    )
    try:
        with TestClient(app_main.app, headers=AUTH) as client:
            response = client.get("/api/examples/secret")
    finally:
        api_app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"configured": True}
    assert "s3cr3t" not in response.text


def test_bound_secret_never_appears_in_settings_output():
    loaded = Settings(
        example_secret="s3cr3t-value",  # pragma: allowlist secret (test fixture)
        _env_file=None,
    )
    assert "s3cr3t" not in repr(loaded)
    assert "s3cr3t" not in loaded.model_dump_json()


def test_bound_secret_requires_identity(monkeypatch):
    monkeypatch.setattr(settings, "enable_local_dev_auth_fallback", False)
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: Settings(
        enable_examples=True, _env_file=None
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.get("/api/examples/secret")
    finally:
        api_app.dependency_overrides.clear()
    assert response.status_code == 401


def test_bound_secret_missing_is_503(monkeypatch):
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: Settings(
        enable_examples=True, _env_file=None
    )
    try:
        with TestClient(app_main.app, headers=AUTH) as client:
            response = client.get("/api/examples/secret")
    finally:
        api_app.dependency_overrides.clear()
    assert response.status_code == 503


def test_examples_require_identity(monkeypatch):
    monkeypatch.setattr(settings, "enable_local_dev_auth_fallback", False)
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: Settings(
        enable_examples=True, _env_file=None
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.post("/api/examples/embed", json={"title": "x"})
    finally:
        api_app.dependency_overrides.clear()
    assert response.status_code == 401


def test_upstream_failures_never_expose_provider_text(monkeypatch):
    """A Databricks SDK error becomes a fixed 502 body with the trace id, not the SDK message."""
    from app.api import examples_controller as examples

    class _Genie:
        def start_conversation(self, *_):
            raise RuntimeError("private-test-diagnostic")

    monkeypatch.setattr(
        examples,
        "get_user_workspace_client",
        lambda request: SimpleNamespace(genie=_Genie()),
    )
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: Settings(
        enable_examples=True, enable_databricks_integrations=True, _env_file=None
    )
    try:
        with TestClient(app_main.app, headers=AUTH) as client:
            response = client.post(
                "/api/examples/genie/space-1/ask", json={"content": "hi"}
            )
    finally:
        api_app.dependency_overrides.clear()
    assert response.status_code == 502
    assert "private-test-diagnostic" not in response.text
    assert set(response.json()) == {"detail", "trace_id"}
