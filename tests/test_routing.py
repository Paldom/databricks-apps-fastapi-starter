from fastapi.testclient import TestClient
import app.main as app_main


AUTH_HEADERS = {"X-Forwarded-User": "test-user"}


def test_legacy_prefix_works():
    with TestClient(app_main.app) as client:
        response = client.get("/legacy/v1/userInfo", headers=AUTH_HEADERS)
    assert response.status_code == 200


def test_api_health_live():
    with TestClient(app_main.app) as client:
        response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_legacy_health_unaffected():
    with TestClient(app_main.app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["status"] == "alive"


def test_api_openapi_has_contract_routes():
    with TestClient(app_main.app) as client:
        response = client.get("/api/openapi.json")
    assert response.status_code == 200
    paths = list(response.json()["paths"].keys())
    assert "/projects" in paths
    assert "/chat/stream" in paths
    assert "/settings" in paths
    assert "/dashboard/stats" in paths


def test_api_openapi_excludes_legacy_routes():
    with TestClient(app_main.app) as client:
        response = client.get("/api/openapi.json")
    assert response.status_code == 200
    paths = list(response.json()["paths"].keys())
    legacy_paths = [p for p in paths if "v1" in p or "todo" in p.lower()]
    assert len(legacy_paths) == 0
