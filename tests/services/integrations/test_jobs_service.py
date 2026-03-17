import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.config import Settings
from app.core.errors import ConfigurationError
from app.services.integrations.jobs_service import JobsService


@pytest.mark.asyncio
async def test_run_delegates_to_adapter():
    adapter = MagicMock()
    adapter.run_and_get_output = AsyncMock(return_value={"result": "ok"})
    settings = Settings(job_id="123")
    service = JobsService(adapter, settings, MagicMock())

    result = await service.run({"key": "val"})

    assert result == {"result": "ok"}
    adapter.run_and_get_output.assert_awaited_once_with(
        job_id=123, notebook_params={"key": "val"}
    )


@pytest.mark.asyncio
async def test_run_raises_when_not_configured():
    adapter = MagicMock()
    settings = Settings(job_id=None)
    service = JobsService(adapter, settings, MagicMock())

    with pytest.raises(ConfigurationError, match="JOB_ID"):
        await service.run()
