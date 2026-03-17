import pytest
from unittest.mock import AsyncMock, MagicMock

import app.core.bootstrap as bootstrap
import app.main as app_main


@pytest.mark.asyncio
async def test_lifespan_calls_dependencies(mocker):
    mock_pool = MagicMock()
    mock_pool.close = AsyncMock()
    mocker.patch.object(
        bootstrap, "create_pg_pool", new=AsyncMock(return_value=mock_pool)
    )

    context_manager = mocker.AsyncMock()
    context_manager.__aenter__.return_value.run_sync = AsyncMock()
    fake_engine = MagicMock()
    fake_engine.begin.return_value = context_manager
    fake_engine.dispose = AsyncMock()
    mocker.patch.object(bootstrap, "create_engine", return_value=fake_engine)
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
        pass

    mock_pool.close.assert_awaited_once()
    context_manager.__aenter__.return_value.run_sync.assert_awaited_once()
    mock_ai.aclose.assert_awaited_once()
    fake_engine.dispose.assert_awaited_once()
