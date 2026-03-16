from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
import main
from modules.todo.controllers import get_service


AUTH_HEADERS = {"X-Forwarded-User": "test-user"}


def test_userinfo_401_without_auth():
    with TestClient(main.app) as client:
        response = client.get("/api/v1/userInfo")
    assert response.status_code == 401


def test_userinfo_200_with_auth():
    with TestClient(main.app) as client:
        response = client.get("/api/v1/userInfo", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-user"


def test_todos_401_without_auth():
    with TestClient(main.app) as client:
        response = client.get("/api/v1/todos/")
    assert response.status_code == 401


def test_todos_200_with_auth():
    mock_service = MagicMock()
    mock_service.list = AsyncMock(return_value=[])
    main.app.dependency_overrides[get_service] = lambda: mock_service
    try:
        with TestClient(main.app) as client:
            response = client.get(
                "/api/v1/todos/",
                headers=AUTH_HEADERS,
            )
        assert response.status_code == 200
    finally:
        main.app.dependency_overrides.clear()


def test_legacy_userinfo_401_without_auth():
    with TestClient(main.app) as client:
        response = client.get("/v1/userInfo")
    assert response.status_code == 401


def test_legacy_todos_401_without_auth():
    with TestClient(main.app) as client:
        response = client.get("/v1/todos/")
    assert response.status_code == 401


def test_request_state_user_set():
    """Verify that authenticated requests populate request.state correctly."""
    with TestClient(main.app) as client:
        response = client.get("/api/v1/userInfo", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-user"
    assert "name" in data


def test_request_state_none_for_unauth():
    """Verify unauthenticated requests get 401 on protected endpoints."""
    with TestClient(main.app) as client:
        response = client.get("/api/v1/userInfo")
    assert response.status_code == 401
