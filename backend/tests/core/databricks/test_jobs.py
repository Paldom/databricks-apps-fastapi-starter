from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.databricks.jobs import JobsAdapter
from app.core.errors import ExternalServiceError, ResourceNotFoundError


@pytest.mark.asyncio
async def test_run_now_returns_the_run_id():
    ws = MagicMock()
    ws.jobs.run_now.return_value = SimpleNamespace(response=SimpleNamespace(run_id=77))
    assert await JobsAdapter(ws, MagicMock()).run_now(5, {"a": "b"}) == 77
    ws.jobs.run_now.assert_called_once_with(job_id=5, notebook_params={"a": "b"})


@pytest.mark.asyncio
async def test_run_state_reports_output_when_finished():
    ws = MagicMock()
    ws.jobs.get_run.return_value = SimpleNamespace(
        job_id=5,
        status=SimpleNamespace(
            state=SimpleNamespace(value="TERMINATED"),
            termination_details=SimpleNamespace(code=SimpleNamespace(value="SUCCESS")),
        ),
        tasks=[SimpleNamespace(run_id=78)],
    )
    ws.jobs.get_run_output.return_value = SimpleNamespace(
        notebook_output=SimpleNamespace(result='{"rows": 3}')
    )
    state = await JobsAdapter(ws, MagicMock(), job_id=5).run_state(77)
    assert state == {
        "run_id": 77,
        "state": "TERMINATED",
        "result": "SUCCESS",
        "output": {"rows": 3},
    }


@pytest.mark.asyncio
async def test_run_state_hides_runs_of_other_jobs():
    ws = MagicMock()
    ws.jobs.get_run.return_value = SimpleNamespace(job_id=6, status=None, tasks=[])
    with pytest.raises(ResourceNotFoundError):
        await JobsAdapter(ws, MagicMock(), job_id=5).run_state(77)


@pytest.mark.asyncio
async def test_sdk_errors_are_wrapped():
    ws = MagicMock()
    ws.jobs.run_now.side_effect = RuntimeError("boom")
    with pytest.raises(ExternalServiceError, match="boom"):
        await JobsAdapter(ws, MagicMock()).run_now(5)
