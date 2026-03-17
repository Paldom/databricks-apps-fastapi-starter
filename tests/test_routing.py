from fastapi.testclient import TestClient
import app.main as app_main


AUTH_HEADERS = {"X-Forwarded-User": "test-user"}


def test_canonical_prefix_works():
    with TestClient(app_main.app) as client:
        response = client.get("/api/v1/userInfo", headers=AUTH_HEADERS)
    assert response.status_code == 200


def test_legacy_prefix_works():
    with TestClient(app_main.app) as client:
        response = client.get("/v1/userInfo", headers=AUTH_HEADERS)
    assert response.status_code == 200


def test_health_unaffected():
    with TestClient(app_main.app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["status"] == "alive"


def test_openapi_has_canonical_prefix():
    with TestClient(app_main.app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = list(response.json()["paths"].keys())
    api_v1_paths = [p for p in paths if p.startswith("/api/v1/")]
    assert len(api_v1_paths) > 0
    assert "/api/v1/userInfo" in paths


def test_openapi_excludes_legacy_prefix():
    with TestClient(app_main.app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = list(response.json()["paths"].keys())
    legacy_paths = [p for p in paths if p.startswith("/v1/")]
    assert len(legacy_paths) == 0
