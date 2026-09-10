"""Showcase routes are gated by ENABLE_EXAMPLES and always require identity."""

from __future__ import annotations

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
