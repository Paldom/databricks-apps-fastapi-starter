import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

import app.core.bootstrap as bootstrap
import app.main as app_main
from app.core.config import Settings


@pytest.mark.asyncio
async def test_lifespan_creates_engine_and_disposes(mocker):
    fake_engine = MagicMock()
    fake_engine.dispose = AsyncMock()
    mocker.patch.object(
        bootstrap,
        "create_async_engine_from_settings",
        return_value=fake_engine,
    )
    mocker.patch.object(bootstrap, "create_session_factory", return_value=MagicMock())
    mocker.patch.object(bootstrap.settings, "enable_databricks_integrations", False)

    async with bootstrap.lifespan(app_main.app):
        runtime = app_main.app.state.runtime
        assert runtime.engine is fake_engine
        assert runtime.session_factory is not None
        assert runtime.workspace_client is None
        assert runtime.ai_client is None
        assert runtime.vector_index is None

    fake_engine.dispose.assert_awaited_once()


def test_health_available_without_databricks_credentials():
    app = app_main.create_app()

    with TestClient(app) as client:
        response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def _build_app(**kwargs):
    return app_main.build_root_app(Settings(**kwargs))


def test_dev_cors_allows_any_origin():
    app = _build_app(environment="development")
    origin = "https://example.test"

    with TestClient(app) as client:
        response = client.get(
            "/api/health/live",
            headers={"Origin": origin},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_dev_cors_handles_preflight():
    app = _build_app(environment="development")
    origin = "https://example.test"

    with TestClient(app) as client:
        response = client.options(
            "/api/health/live",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_non_dev_app_does_not_enable_cors():
    app = _build_app(environment="production")

    with TestClient(app) as client:
        response = client.get(
            "/api/health/live",
            headers={"Origin": "https://example.test"},
        )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
