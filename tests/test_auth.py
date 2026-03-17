from fastapi.testclient import TestClient
import app.main as app_main


AUTH_HEADERS = {"X-Forwarded-User": "test-user"}


def test_userinfo_401_without_auth():
    with TestClient(app_main.app) as client:
        response = client.get("/legacy/v1/userInfo")
    assert response.status_code == 401


def test_userinfo_200_with_auth():
    with TestClient(app_main.app) as client:
        response = client.get("/legacy/v1/userInfo", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-user"


def test_request_state_user_set():
    with TestClient(app_main.app) as client:
        response = client.get("/legacy/v1/userInfo", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-user"
    assert "name" in data


def test_request_state_none_for_unauth():
    with TestClient(app_main.app) as client:
        response = client.get("/legacy/v1/userInfo")
    assert response.status_code == 401
