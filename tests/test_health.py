from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import app.api.health_controller as health_controller
import app.main as app_main
from app.core.config import Settings
from app.core.deps import get_settings


def _db_settings(**kwargs) -> Settings:
    return Settings(
        lakebase_host="db.example.com",
        lakebase_db="starter",
        lakebase_user="starter",
        lakebase_password="secret",
        **kwargs,
    )


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
        health_controller,
        "_probe_database",
        AsyncMock(return_value="SELECT 1 succeeded"),
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
    assert data["checks"]["database"]["status"] == "ok"
    assert data["checks"]["database"]["message"] == "SELECT 1 succeeded"
    assert data["checks"]["database"]["latency_ms"] is not None


def test_databasehealthcheck_returns_not_ready_when_db_probe_fails(monkeypatch):
    app_main.app.dependency_overrides[get_settings] = lambda: _db_settings()
    monkeypatch.setattr(
        health_controller,
        "_probe_database",
        AsyncMock(side_effect=RuntimeError("db down")),
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.get("/databasehealthcheck")
    finally:
        app_main.app.dependency_overrides.clear()

    data = response.json()
    assert response.status_code == 503
    assert data["ok"] is False
    assert data["status"] == "not_ready"
    assert data["checks"]["database"]["status"] == "fail"
    assert "db down" in data["checks"]["database"]["message"]


def test_ready_returns_degraded_when_optional_integrations_are_not_configured(
    monkeypatch,
):
    app_main.app.dependency_overrides[get_settings] = lambda: _db_settings()
    monkeypatch.setattr(
        health_controller,
        "_probe_database",
        AsyncMock(return_value="SELECT 1 succeeded"),
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.get("/health/ready")
    finally:
        app_main.app.dependency_overrides.clear()

    data = response.json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["status"] == "degraded"
    assert data["checks"]["database"]["status"] == "ok"
    assert data["checks"]["database"]["latency_ms"] is not None
    assert data["checks"]["ai"]["status"] == "not_configured"
    assert data["checks"]["ai"]["message"] == "SERVING_ENDPOINT_NAME is not set"
    assert data["checks"]["vector_search"]["status"] == "not_configured"
    assert (
        data["checks"]["vector_search"]["message"]
        == "VECTOR_SEARCH_ENDPOINT_NAME and VECTOR_SEARCH_INDEX_NAME are not set"
    )
    assert data["checks"]["cache"]["status"] == "not_configured"
    assert data["checks"]["broker"]["status"] == "not_configured"


def test_ready_returns_not_ready_when_database_probe_fails(monkeypatch):
    app_main.app.dependency_overrides[get_settings] = lambda: _db_settings()
    monkeypatch.setattr(
        health_controller,
        "_probe_database",
        AsyncMock(side_effect=RuntimeError("db down")),
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
    assert data["checks"]["database"]["status"] == "fail"


def test_ready_returns_not_ready_when_database_is_not_configured():
    app_main.app.dependency_overrides[get_settings] = lambda: Settings()
    try:
        with TestClient(app_main.app) as client:
            response = client.get("/health/ready")
    finally:
        app_main.app.dependency_overrides.clear()

    data = response.json()
    assert response.status_code == 503
    assert data["ok"] is False
    assert data["status"] == "not_ready"
    assert data["checks"]["database"]["status"] == "not_configured"
    assert (
        data["checks"]["database"]["message"]
        == "DATABASE_URL or LAKEBASE_* settings are not configured"
    )


def test_ready_is_lightweight_no_network_call(monkeypatch):
    """Readiness endpoint should NOT call _probe_ai or _probe_vector."""
    app_main.app.dependency_overrides[get_settings] = lambda: _db_settings(
        serving_endpoint_name="starter-endpoint",
        vector_search_endpoint_name="starter-vs",
        vector_search_index_name="main.default.starter_index",
    )
    monkeypatch.setattr(
        health_controller,
        "_probe_database",
        AsyncMock(return_value="SELECT 1 succeeded"),
    )
    probe_ai_mock = AsyncMock(return_value="Embedding request succeeded")
    monkeypatch.setattr(health_controller, "_probe_ai", probe_ai_mock)
    probe_vector_mock = AsyncMock(return_value="Vector Search describe succeeded")
    monkeypatch.setattr(health_controller, "_probe_vector", probe_vector_mock)
    try:
        with TestClient(app_main.app) as client:
            response = client.get("/health/ready")
    finally:
        app_main.app.dependency_overrides.clear()

    data = response.json()
    assert response.status_code == 200
    # Lightweight ready: AI and vector should show as OK (initialized)
    # but the probes should NOT have been called
    assert data["checks"]["ai"]["status"] == "ok"
    assert data["checks"]["ai"]["message"] == "AI client initialized"
    assert data["checks"]["vector_search"]["status"] == "ok"
    assert data["checks"]["vector_search"]["message"] == "Vector Search index initialized"
    probe_ai_mock.assert_not_called()
    probe_vector_mock.assert_not_called()


def test_deep_health_returns_full_probes(monkeypatch):
    """Deep health endpoint should run actual probes."""
    app_main.app.dependency_overrides[get_settings] = lambda: _db_settings()
    monkeypatch.setattr(
        health_controller,
        "_probe_database",
        AsyncMock(return_value="SELECT 1 succeeded"),
    )
    try:
        with TestClient(app_main.app) as client:
            # Reset cache to force fresh probes
            runtime = client.app.state.runtime
            runtime.last_deep_health = None
            response = client.get("/health/deep")
    finally:
        app_main.app.dependency_overrides.clear()

    data = response.json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["checks"]["database"]["status"] == "ok"


def test_deep_health_uses_cache(monkeypatch):
    """Subsequent /health/deep calls should return cached results within TTL."""
    app_main.app.dependency_overrides[get_settings] = lambda: _db_settings()
    monkeypatch.setattr(
        health_controller,
        "_probe_database",
        AsyncMock(return_value="SELECT 1 succeeded"),
    )
    try:
        with TestClient(app_main.app) as client:
            runtime = client.app.state.runtime
            runtime.last_deep_health = None
            resp1 = client.get("/health/deep")
            resp2 = client.get("/health/deep")
    finally:
        app_main.app.dependency_overrides.clear()

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()


def test_ready_reports_vector_failure_without_crashing(monkeypatch):
    app_main.app.dependency_overrides[get_settings] = lambda: _db_settings(
        vector_search_endpoint_name="starter-vs",
        vector_search_index_name="main.default.starter_index",
    )
    monkeypatch.setattr(
        health_controller,
        "_probe_database",
        AsyncMock(return_value="SELECT 1 succeeded"),
    )
    try:
        with TestClient(app_main.app) as client:
            runtime = client.app.state.runtime
            runtime.vector_index = None
            runtime.remember_error("vector_index", "vector index init failed")
            response = client.get("/health/ready")
    finally:
        app_main.app.dependency_overrides.clear()

    data = response.json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["status"] == "degraded"
    assert data["checks"]["vector_search"]["status"] == "fail"
    assert data["checks"]["vector_search"]["message"] == "vector index init failed"
