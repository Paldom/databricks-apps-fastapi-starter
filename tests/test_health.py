from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

import app.core.health as health_core
import app.main as app_main
from app.core.config import Settings, settings
from app.core.deps import get_settings
from app.core.errors import ServiceUnavailableError
from app.models.health_dto import DependencyHealth, DependencyHealthStatus


def _db_settings(**kwargs) -> Settings:
    return Settings(
        lakebase_host="db.example.com",
        lakebase_db="starter",
        lakebase_user="starter",
        lakebase_password="secret",
        **kwargs,
    )


def _db_result(status: DependencyHealthStatus, reason: str) -> DependencyHealth:
    return DependencyHealth(status=status, required=True, reason=reason)


def test_health_live_aliases_match():
    with TestClient(app_main.app) as client:
        healthcheck = client.get("/healthcheck")
        live = client.get("/health/live")

    assert healthcheck.status_code == 200
    assert live.status_code == 200
    assert healthcheck.json() == live.json()


def test_databasehealthcheck_returns_ready_when_db_probe_succeeds(monkeypatch):
    app_main.app.dependency_overrides[get_settings] = lambda: _db_settings()
    monkeypatch.setattr(
        health_core,
        "_database_dependency",
        AsyncMock(return_value=_db_result(DependencyHealthStatus.OK, "SELECT 1 succeeded")),
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.get("/databasehealthcheck")
    finally:
        app_main.app.dependency_overrides.clear()

    data = response.json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["status"] == "ready"
    assert data["db"]["status"] == "ok"
    assert data["db"]["reason"] == "SELECT 1 succeeded"


def test_ready_returns_not_ready_when_database_is_not_configured(monkeypatch):
    app_main.app.dependency_overrides[get_settings] = lambda: Settings()
    monkeypatch.setattr(
        health_core,
        "_database_dependency",
        AsyncMock(
            return_value=_db_result(
                DependencyHealthStatus.NOT_CONFIGURED,
                "DATABASE_URL, PG*, or LAKEBASE_* settings are not configured",
            )
        ),
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.get("/health/ready")
    finally:
        app_main.app.dependency_overrides.clear()

    data = response.json()
    assert response.status_code == 503
    assert data["ok"] is False
    assert data["status"] == "not_ready"
    assert data["db"]["status"] == "not_configured"


def test_api_ready_only_checks_core_database(monkeypatch):
    app_main.app.dependency_overrides[get_settings] = lambda: _db_settings(
        enable_databricks_integrations=True,
        serving_endpoint_name="starter-endpoint",
        vector_search_endpoint_name="starter-vs",
        vector_search_index_name="main.default.starter_index",
    )
    monkeypatch.setattr(
        health_core,
        "_database_dependency",
        AsyncMock(return_value=_db_result(DependencyHealthStatus.OK, "SELECT 1 succeeded")),
    )
    monkeypatch.setattr(
        health_core,
        "ensure_workspace_client",
        lambda *_: (_ for _ in ()).throw(AssertionError("workspace should not be called")),
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.get("/api/health/ready")
    finally:
        app_main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_integrations_reports_disabled_when_offline(monkeypatch):
    monkeypatch.setattr(settings, "enable_databricks_integrations", False)

    with TestClient(app_main.app) as client:
        response = client.get("/api/health/integrations")

    data = response.json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["status"] == "degraded"
    assert data["workspace"]["status"] == "disabled"
    assert data["workspace"]["disabled"] is True
    assert data["ai"]["status"] == "disabled"
    assert data["vector_search"]["status"] == "disabled"


def test_integrations_report_ok_when_resources_initialize(monkeypatch):
    monkeypatch.setattr(settings, "enable_databricks_integrations", True)
    monkeypatch.setattr(settings, "serving_endpoint_name", "starter-endpoint")
    monkeypatch.setattr(settings, "vector_search_endpoint_name", "starter-vs")
    monkeypatch.setattr(settings, "vector_search_index_name", "main.default.starter_index")
    monkeypatch.setattr(health_core, "ensure_workspace_client", lambda *_: MagicMock())
    monkeypatch.setattr(health_core, "ensure_ai_client", lambda *_: MagicMock())
    monkeypatch.setattr(health_core, "ensure_vector_index", lambda *_: MagicMock())

    with TestClient(app_main.app) as client:
        response = client.get("/api/health/integrations")

    data = response.json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["status"] == "ready"
    assert data["workspace"]["status"] == "ok"
    assert data["ai"]["status"] == "ok"
    assert data["vector_search"]["status"] == "ok"


def test_integrations_report_failure_without_crashing(monkeypatch):
    monkeypatch.setattr(settings, "enable_databricks_integrations", True)
    monkeypatch.setattr(settings, "serving_endpoint_name", "starter-endpoint")
    monkeypatch.setattr(settings, "vector_search_endpoint_name", "starter-vs")
    monkeypatch.setattr(settings, "vector_search_index_name", "main.default.starter_index")
    monkeypatch.setattr(
        health_core,
        "ensure_workspace_client",
        lambda *_: (_ for _ in ()).throw(
            ServiceUnavailableError("Databricks workspace client is unavailable: boom")
        ),
    )
    monkeypatch.setattr(health_core, "ensure_ai_client", lambda *_: MagicMock())
    monkeypatch.setattr(health_core, "ensure_vector_index", lambda *_: MagicMock())

    with TestClient(app_main.app) as client:
        response = client.get("/health/integrations")

    data = response.json()
    assert response.status_code == 503
    assert data["ok"] is False
    assert data["status"] == "degraded"
    assert data["workspace"]["status"] == "fail"
    assert "boom" in data["workspace"]["reason"]
