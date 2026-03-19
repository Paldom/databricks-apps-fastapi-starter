from pathlib import Path

from fastapi.testclient import TestClient

import app.main as app_main
from app.core.config import Settings


AUTH_HEADERS = {"X-Forwarded-User": "test-user"}


def test_legacy_prefix_removed():
    with TestClient(app_main.app) as client:
        response = client.get("/legacy/v1/userInfo", headers=AUTH_HEADERS)
    assert response.status_code == 404


def test_api_me_route_works():
    with TestClient(app_main.app) as client:
        response = client.get("/api/me", headers=AUTH_HEADERS)
    assert response.status_code == 200


def test_api_health_live_route_works():
    with TestClient(app_main.app) as client:
        response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_api_openapi_has_contract_routes():
    with TestClient(app_main.app) as client:
        response = client.get("/api/openapi.json")
    assert response.status_code == 200
    paths = list(response.json()["paths"].keys())
    assert "/health" in paths
    assert "/examples/job" in paths
    assert "/projects" in paths
    assert "/chat/stream" in paths
    assert "/me" in paths
    assert "/settings" in paths


def test_api_openapi_excludes_legacy_routes():
    with TestClient(app_main.app) as client:
        response = client.get("/api/openapi.json")
    assert response.status_code == 200
    paths = list(response.json()["paths"].keys())
    legacy_paths = [p for p in paths if "legacy" in p or "v1" in p]
    assert len(legacy_paths) == 0


def test_spa_fallback_serves_index_for_unknown_non_api_route(tmp_path):
    index_file = tmp_path / "index.html"
    index_file.write_text("<html>starter</html>", encoding="utf-8")
    app = app_main.build_root_app(
        Settings(serve_static=True, frontend_dist_dir=str(tmp_path))
    )
    with TestClient(app) as client:
        response = client.get("/app/projects/123")
    assert response.status_code == 200
    assert response.text == "<html>starter</html>"
    assert response.headers["cache-control"].startswith("no-store")
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"


def test_unknown_api_route_stays_json_404_for_static_app(tmp_path):
    index_file = Path(tmp_path) / "index.html"
    index_file.write_text("<html>starter</html>", encoding="utf-8")
    app = app_main.build_root_app(
        Settings(serve_static=True, frontend_dist_dir=str(tmp_path))
    )
    with TestClient(app) as client:
        response = client.get("/api/not-found")
    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"
