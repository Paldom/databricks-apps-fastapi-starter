from fastapi.testclient import TestClient

import app.main as app_main
from app.core.config import Settings
from app.core.deps import get_settings


def test_embed_returns_503_when_ai_is_not_configured():
    app_main.app.dependency_overrides[get_settings] = lambda: Settings()
    try:
        with TestClient(app_main.app) as client:
            response = client.post("/legacy/v1/embed", json={"title": "hello"})
    finally:
        app_main.app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "SERVING_ENDPOINT_NAME" in response.json()["detail"]


def test_serving_returns_503_when_endpoint_is_not_configured():
    app_main.app.dependency_overrides[get_settings] = lambda: Settings()
    try:
        with TestClient(app_main.app) as client:
            response = client.post(
                "/legacy/v1/serving",
                json=[{"id": "1", "data": "hello"}],
            )
    finally:
        app_main.app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "SERVING_ENDPOINT_NAME" in response.json()["detail"]


def test_job_returns_503_when_job_id_is_not_configured():
    app_main.app.dependency_overrides[get_settings] = lambda: Settings()
    try:
        with TestClient(app_main.app) as client:
            response = client.post("/legacy/v1/job")
    finally:
        app_main.app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "JOB_ID" in response.json()["detail"]


def test_vector_query_returns_clean_503_when_index_is_unavailable():
    app_main.app.dependency_overrides[get_settings] = lambda: Settings(
        serving_endpoint_name="starter-endpoint",
        vector_search_endpoint_name="starter-vs",
        vector_search_index_name="main.default.starter_index",
    )
    try:
        with TestClient(app_main.app) as client:
            runtime = client.app.state.runtime
            runtime.vector_index = None
            runtime.remember_error("vector_index", "vector index init failed")
            response = client.post("/legacy/v1/vector/query", json={"title": "hello"})
    finally:
        app_main.app.dependency_overrides.clear()

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "Vector Search index is unavailable" in detail
    assert "RuntimeError" not in detail


def test_agent_ask_returns_503_when_endpoint_not_configured():
    app_main.app.dependency_overrides[get_settings] = lambda: Settings()
    try:
        with TestClient(app_main.app) as client:
            response = client.post(
                "/legacy/v1/agent/ask",
                json={"messages": [{"role": "user", "content": "hello"}]},
            )
    finally:
        app_main.app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "KNOWLEDGE_ASSISTANT_ENDPOINT" in response.json()["detail"]


def test_vector_store_returns_clean_503_when_index_is_unavailable():
    app_main.app.dependency_overrides[get_settings] = lambda: Settings(
        serving_endpoint_name="starter-endpoint",
        vector_search_endpoint_name="starter-vs",
        vector_search_index_name="main.default.starter_index",
    )
    try:
        with TestClient(app_main.app) as client:
            runtime = client.app.state.runtime
            runtime.vector_index = None
            runtime.remember_error("vector_index", "vector index init failed")
            response = client.post("/legacy/v1/vector/store", json={"title": "hello"})
    finally:
        app_main.app.dependency_overrides.clear()

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "Vector Search index is unavailable" in detail
    assert "RuntimeError" not in detail
