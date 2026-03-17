import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

import app.core.bootstrap as bootstrap
import app.main as app_main


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

    wc = MagicMock()
    wc.config.token = "t"
    wc.config.host = "http://h"
    mocker.patch.object(bootstrap, "get_workspace_client_singleton", return_value=wc)

    mock_ai = MagicMock()
    mock_ai.aclose = AsyncMock()
    mocker.patch.object(bootstrap, "AsyncOpenAI", return_value=mock_ai)
    mocker.patch.object(bootstrap, "init_vector_index", return_value=MagicMock())
    mocker.patch.object(bootstrap.settings, "lakebase_host", "db.example.com")
    mocker.patch.object(bootstrap.settings, "lakebase_db", "starter")
    mocker.patch.object(bootstrap.settings, "lakebase_user", "starter")
    mocker.patch.object(bootstrap.settings, "lakebase_password", "secret")
    mocker.patch.object(bootstrap.settings, "serving_endpoint_name", "starter-endpoint")
    mocker.patch.object(
        bootstrap.settings, "vector_search_endpoint_name", "starter-vs"
    )
    mocker.patch.object(
        bootstrap.settings,
        "vector_search_index_name",
        "main.default.starter_index",
    )

    async with bootstrap.lifespan(app_main.app):
        runtime = app_main.app.state.runtime
        assert runtime.engine is fake_engine
        assert runtime.session_factory is not None
        assert runtime.ai_client is mock_ai

    # Shutdown should dispose engine and close AI client
    fake_engine.dispose.assert_awaited_once()
    mock_ai.aclose.assert_awaited_once()


def test_healthcheck_available_when_workspace_init_fails(mocker):
    mocker.patch.object(
        bootstrap,
        "get_workspace_client_singleton",
        side_effect=RuntimeError("workspace unavailable"),
    )
    app = app_main.create_app()

    with TestClient(app) as client:
        response = client.get("/healthcheck")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"


@pytest.mark.asyncio
async def test_shutdown_only_closes_created_resources(mocker):
    fake_engine = MagicMock()
    fake_engine.dispose = AsyncMock()
    mocker.patch.object(
        bootstrap,
        "create_async_engine_from_settings",
        return_value=fake_engine,
    )
    mocker.patch.object(bootstrap, "create_session_factory", return_value=MagicMock())
    mocker.patch.object(
        bootstrap,
        "get_workspace_client_singleton",
        side_effect=RuntimeError("workspace unavailable"),
    )
    mock_ai_factory = mocker.patch.object(bootstrap, "AsyncOpenAI")
    mocker.patch.object(
        bootstrap, "init_vector_index", side_effect=RuntimeError("vector unavailable")
    )
    app = app_main.create_app()

    async with bootstrap.lifespan(app):
        runtime = app.state.runtime
        assert runtime.engine is fake_engine
        assert runtime.ai_client is None

    fake_engine.dispose.assert_awaited_once()
    mock_ai_factory.assert_not_called()
