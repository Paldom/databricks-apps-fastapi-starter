import pytest
from unittest.mock import AsyncMock, MagicMock

import main


@pytest.mark.asyncio
async def test_lifespan_calls_dependencies(mocker):
    mock_init_pg_pool = mocker.patch.object(main, "init_pg_pool", new=AsyncMock())
    mock_close_pg_pool = mocker.patch.object(main, "close_pg_pool", new=AsyncMock())
    context_manager = mocker.AsyncMock()
    context_manager.__aenter__.return_value.run_sync = AsyncMock()
    mocker.patch.object(main.engine, "begin", return_value=context_manager)
    mock_dispose = mocker.patch.object(main.engine, "dispose", new=AsyncMock())

    wc = MagicMock()
    wc.config.token = "t"
    wc.config.host = "http://h"
    mocker.patch.object(main, "get_workspace_client", return_value=wc)

    mock_ai = MagicMock()
    mock_ai.aclose = AsyncMock()
    mocker.patch.object(main, "AsyncOpenAI", return_value=mock_ai)
    mocker.patch.object(main, "init_vector_index")
    mocker.patch.object(main, "vector_index", MagicMock())

    async with main.lifespan(main.app):
        # No actions inside the context; we only verify lifecycle hooks.
        pass

    mock_init_pg_pool.assert_awaited_once()
    context_manager.__aenter__.return_value.run_sync.assert_awaited_once()
    mock_ai.aclose.assert_awaited_once()
    mock_close_pg_pool.assert_awaited_once()
    mock_dispose.assert_awaited_once()

