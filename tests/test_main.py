import pytest
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

    async with bootstrap.lifespan(app_main.app):
        # Engine and session factory should be set on app state
        assert app_main.app.state.engine is fake_engine
        assert app_main.app.state.session_factory is not None

    # Shutdown should dispose engine and close AI client
    fake_engine.dispose.assert_awaited_once()
    mock_ai.aclose.assert_awaited_once()
