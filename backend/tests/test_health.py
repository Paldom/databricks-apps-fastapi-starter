from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import app.main as app_main
from app.core.config import Settings
from app.core.deps import get_settings


def _api_app():
    for route in app_main.app.routes:
        if getattr(route, "path", None) == "/api":
            return route.app
    raise AssertionError("Mounted /api app not found")


def _db_settings(**kwargs) -> Settings:
    return Settings(
        pg_host="db.example.com",
        pg_database="starter",
        pg_user="starter",
        pg_password="secret",
        **kwargs,
    )


def test_health_live_always_ok():
    with TestClient(app_main.app) as client:
        response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_health_ready_503_when_no_db(monkeypatch):
    """When the runtime has no engine, /health/ready returns 503."""
    with TestClient(app_main.app) as client:
        # Override the runtime to have no engine
        client.app.state.runtime.engine = None
        response = client.get("/api/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["ok"] is False
    assert data["db"] is False


def test_health_detailed_reports_all_deps():
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: _db_settings(
        enable_databricks_integrations=False
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.get("/api/health")
    finally:
        api_app.dependency_overrides.clear()

    data = response.json()
    assert data["ok"] is True
    # Integrations disabled → ok with reason "Disabled"
    assert data["workspace"]["status"] == "ok"
    assert data["workspace"]["reason"] == "Disabled"
    assert data["ai"]["status"] == "ok"
    assert data["vector_search"]["status"] == "ok"
