from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

import app.main as app_main
from app.core.config import Settings
from app.core.deps import get_settings


def _api_app():
    for route in app_main.app.routes:
        if getattr(route, "path", None) == "/api":
            return route.app
    raise AssertionError("Mounted /api app not found")


def test_embed_returns_503_when_integrations_are_disabled():
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: Settings(
        serving_endpoint_name="starter-endpoint"
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.post("/api/examples/embed", json={"title": "hello"})
    finally:
        api_app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "ENABLE_DATABRICKS_INTEGRATIONS" in response.json()["detail"]


def test_serving_returns_503_when_integrations_are_disabled():
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: Settings(
        serving_endpoint_name="starter-endpoint"
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/examples/serving",
                json=[{"id": "1", "data": "hello"}],
            )
    finally:
        api_app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "ENABLE_DATABRICKS_INTEGRATIONS" in response.json()["detail"]


def test_job_returns_503_when_job_id_is_not_configured():
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: Settings(
        enable_databricks_integrations=True
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.post("/api/examples/job")
    finally:
        api_app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "JOB_ID" in response.json()["detail"]


def test_vector_query_returns_503_when_integrations_are_disabled():
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: Settings(
        serving_endpoint_name="starter-endpoint",
        vector_search_endpoint_name="starter-vs",
        vector_search_index_name="main.default.starter_index",
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/examples/vector/query", json={"title": "hello"}
            )
    finally:
        api_app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "ENABLE_DATABRICKS_INTEGRATIONS" in response.json()["detail"]


def test_agent_ask_returns_503_when_integrations_are_disabled():
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: Settings(
        knowledge_assistant_endpoint="starter-agent"
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/examples/agent/ask",
                json={"messages": [{"role": "user", "content": "hello"}]},
            )
    finally:
        api_app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "ENABLE_DATABRICKS_INTEGRATIONS" in response.json()["detail"]


def test_vector_store_returns_503_when_integrations_are_disabled():
    api_app = _api_app()
    api_app.dependency_overrides[get_settings] = lambda: Settings(
        serving_endpoint_name="starter-endpoint",
        vector_search_endpoint_name="starter-vs",
        vector_search_index_name="main.default.starter_index",
    )
    try:
        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/examples/vector/store", json={"title": "hello"}
            )
    finally:
        api_app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "ENABLE_DATABRICKS_INTEGRATIONS" in response.json()["detail"]
