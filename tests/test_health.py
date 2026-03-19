from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

import app.core.health as health_core
import app.main as app_main
from app.core.config import Settings
from app.core.deps import get_settings
from app.core.errors import ServiceUnavailableError
from app.models.health_dto import DependencyHealth, DependencyHealthStatus


def _api_app():
    for route in app_main.app.routes:
        if getattr(route, "path", None) == "/api":
            return route.app
    raise AssertionError("Mounted /api app not found")


def _db_settings(**kwargs) -> Settings:
    return Settings(
        lakebase_host="db.example.com",
        lakebase_db="starter",
        lakebase_user="starter",
        lakebase_password="secret",
        **kwargs,
    )


def _dep(status: DependencyHealthStatus, reason: str) -> DependencyHealth:
    return DependencyHealth(status=status, required=True, reason=reason)


def test_health_degraded_when_integrations_are_disabled(monkeypatch):
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: _db_settings(
        enable_databricks_integrations=False
    )
    monkeypatch.setattr(
        health_core,
        "_database_dependency",
        AsyncMock(return_value=_dep(DependencyHealthStatus.OK, "SELECT 1 succeeded")),
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.get("/api/health")
    finally:
        api_app.dependency_overrides.clear()

    data = response.json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["status"] == "degraded"
    assert data["checks"]["database"]["status"] == "ok"
    assert data["checks"]["workspace"]["status"] == "disabled"
    assert data["checks"]["ai"]["status"] == "disabled"
    assert data["checks"]["vector_search"]["status"] == "disabled"


def test_health_ok_when_all_configured_checks_pass(monkeypatch):
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: _db_settings(
        enable_databricks_integrations=True,
        serving_endpoint_name="starter-endpoint",
        vector_search_endpoint_name="starter-vs",
        vector_search_index_name="main.default.starter_index",
        job_id="123",
        knowledge_assistant_endpoint="starter-agent",
    )
    monkeypatch.setattr(
        health_core,
        "_database_dependency",
        AsyncMock(return_value=_dep(DependencyHealthStatus.OK, "SELECT 1 succeeded")),
    )
    monkeypatch.setattr(health_core, "ensure_workspace_client", lambda *_: MagicMock())
    monkeypatch.setattr(health_core, "ensure_ai_client", lambda *_: MagicMock())
    monkeypatch.setattr(health_core, "ensure_vector_index", lambda *_: MagicMock())
    try:
        with TestClient(app_main.app) as client:
            response = client.get("/api/health")
    finally:
        api_app.dependency_overrides.clear()

    data = response.json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["status"] == "ok"
    assert data["checks"]["workspace"]["status"] == "ok"
    assert data["checks"]["ai"]["status"] == "ok"
    assert data["checks"]["vector_search"]["status"] == "ok"
    assert data["checks"]["jobs"]["status"] == "ok"
    assert data["checks"]["knowledge_assistant"]["status"] == "ok"


def test_health_fails_when_database_is_not_configured(monkeypatch):
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: Settings()
    monkeypatch.setattr(
        health_core,
        "_database_dependency",
        AsyncMock(
            return_value=_dep(
                DependencyHealthStatus.NOT_CONFIGURED,
                "DATABASE_URL, PG*, or LAKEBASE_* settings are not configured",
            )
        ),
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.get("/api/health")
    finally:
        api_app.dependency_overrides.clear()

    data = response.json()
    assert response.status_code == 503
    assert data["ok"] is False
    assert data["status"] == "fail"
    assert data["checks"]["database"]["status"] == "not_configured"


def test_health_fails_when_workspace_dependency_errors(monkeypatch):
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: _db_settings(
        enable_databricks_integrations=True,
        serving_endpoint_name="starter-endpoint",
        vector_search_endpoint_name="starter-vs",
        vector_search_index_name="main.default.starter_index",
        job_id="123",
        knowledge_assistant_endpoint="starter-agent",
    )
    monkeypatch.setattr(
        health_core,
        "_database_dependency",
        AsyncMock(return_value=_dep(DependencyHealthStatus.OK, "SELECT 1 succeeded")),
    )
    monkeypatch.setattr(
        health_core,
        "ensure_workspace_client",
        lambda *_: (_ for _ in ()).throw(
            ServiceUnavailableError("Databricks workspace client is unavailable: boom")
        ),
    )
    monkeypatch.setattr(health_core, "ensure_ai_client", lambda *_: MagicMock())
    monkeypatch.setattr(health_core, "ensure_vector_index", lambda *_: MagicMock())
    try:
        with TestClient(app_main.app) as client:
            response = client.get("/api/health")
    finally:
        api_app.dependency_overrides.clear()

    data = response.json()
    assert response.status_code == 503
    assert data["ok"] is False
    assert data["status"] == "fail"
    assert data["checks"]["workspace"]["status"] == "fail"
    assert "boom" in data["checks"]["workspace"]["reason"]
