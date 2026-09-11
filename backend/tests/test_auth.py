from fastapi.testclient import TestClient

import app.main as app_main
from app.core.config import settings

ME_HEADERS = {
    "X-Forwarded-User": "test-user",
    "X-Forwarded-Email": "user@example.com",
    "X-Forwarded-Preferred-Username": "test.user",
}


def test_me_401_without_auth_when_fallback_disabled(monkeypatch):
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "enable_local_dev_auth_fallback", False)

    with TestClient(app_main.app) as client:
        response = client.get("/api/me")

    assert response.status_code == 401


def test_me_200_with_auth_headers():
    with TestClient(app_main.app) as client:
        response = client.get("/api/me", headers=ME_HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "id": "test-user",
        "email": "user@example.com",
        "name": "test.user",
        "preferred_username": "test.user",
    }


def test_me_uses_local_dev_fallback(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "enable_local_dev_auth_fallback", None)
    monkeypatch.setattr(settings, "local_dev_user_id", "local-dev-user")

    with TestClient(app_main.app) as client:
        response = client.get("/api/me")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "local-dev-user"
    assert data["name"] == "local-dev-user"
    assert data["preferred_username"] == "local-dev-user"


def test_api_route_uses_local_dev_fallback(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "enable_local_dev_auth_fallback", None)
    monkeypatch.setattr(settings, "local_dev_user_id", "local-dev-user")

    with TestClient(app_main.app) as client:
        response = client.get("/api/me")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "local-dev-user"


def test_me_decodes_utf8_forwarded_name():
    # The Apps proxy forwards UTF-8 names as raw bytes; HTTP decodes headers
    # as latin-1, so "Pál" arrives as "PÃ¡l" unless re-decoded.
    headers = [
        (k, v) for k, v in ME_HEADERS.items() if k != "X-Forwarded-Preferred-Username"
    ] + [(b"X-Forwarded-Preferred-Username", "Domonkos Pál".encode())]
    with TestClient(app_main.app) as client:
        response = client.get("/api/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Domonkos Pál"
