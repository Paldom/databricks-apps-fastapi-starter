import pytest
from unittest.mock import MagicMock

from app.core.databricks.jobs import JobsAdapter
from app.core.errors import JobExecutionError


@pytest.mark.asyncio
async def test_run_and_get_output_success():
    ws = MagicMock()
    finished = MagicMock()
    finished.tasks = [MagicMock(run_id=42)]
    ws.jobs.run_now_and_wait.return_value = finished

    out = MagicMock()
    out.notebook_output.result = '{"result": "ok"}'
    ws.jobs.get_run_output.return_value = out

    adapter = JobsAdapter(ws, MagicMock())
    result = await adapter.run_and_get_output(123, {"key": "val"})

    assert result == {"result": "ok"}
    ws.jobs.run_now_and_wait.assert_called_once()
    ws.jobs.get_run_output.assert_called_once_with(run_id=42)


@pytest.mark.asyncio
async def test_run_wraps_sdk_error():
    ws = MagicMock()
    ws.jobs.run_now_and_wait.side_effect = RuntimeError("fail")
    adapter = JobsAdapter(ws, MagicMock())
    with pytest.raises(JobExecutionError, match="fail"):
        await adapter.run_and_get_output(1)


@pytest.mark.asyncio
async def test_run_raises_on_bad_output():
    ws = MagicMock()
    finished = MagicMock()
    finished.tasks = [MagicMock(run_id=1)]
    ws.jobs.run_now_and_wait.return_value = finished

    out = MagicMock()
    out.notebook_output.result = "not-json"
    ws.jobs.get_run_output.return_value = out

    adapter = JobsAdapter(ws, MagicMock())
    with pytest.raises(JobExecutionError, match="Failed to parse"):
        await adapter.run_and_get_output(1)
