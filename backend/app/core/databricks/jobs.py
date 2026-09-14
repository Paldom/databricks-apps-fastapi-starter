import json
from logging import Logger

from databricks.sdk import WorkspaceClient

from app.core.databricks._async_bridge import run_sync
from app.core.errors import ExternalServiceError, ResourceNotFoundError
from app.core.observability import get_tracer


_tracer = get_tracer()


class JobsAdapter:
    def __init__(self, ws: WorkspaceClient, logger: Logger, job_id: int | None = None):
        self._ws = ws
        self._logger = logger
        self._job_id = job_id  # when set, only runs of this job are visible

    async def run_now(
        self, job_id: int, notebook_params: dict[str, str] | None = None
    ) -> int:
        """Start a run and return its id (poll with ``run_state``)."""
        waiter = await run_sync(
            self._ws.jobs.run_now,
            job_id=job_id,
            notebook_params=notebook_params or {},
            error_cls=ExternalServiceError,
        )
        return int(waiter.response.run_id)

    async def run_state(self, run_id: int) -> dict:
        """Lifecycle/result state of a run plus its notebook output when finished."""
        run = await run_sync(
            self._ws.jobs.get_run, run_id=run_id, error_cls=ExternalServiceError
        )
        if (
            self._job_id is not None
            and int(getattr(run, "job_id", 0) or 0) != self._job_id
        ):
            raise ResourceNotFoundError("Run not found")
        status = getattr(run, "status", None)
        state = str(getattr(getattr(status, "state", None), "value", "") or "")
        details = getattr(status, "termination_details", None)
        result = str(getattr(getattr(details, "code", None), "value", "") or "")
        output = None
        if state == "TERMINATED" and run.tasks:
            out = await run_sync(
                self._ws.jobs.get_run_output,
                run_id=run.tasks[-1].run_id,
                error_cls=ExternalServiceError,
            )
            try:
                output = json.loads(out.notebook_output.result)
            except (json.JSONDecodeError, AttributeError, TypeError):
                output = None
        return {"run_id": run_id, "state": state, "result": result, "output": output}
