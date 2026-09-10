import json
from logging import Logger

from databricks.sdk import WorkspaceClient

from app.core.databricks._async_bridge import run_sync
from app.core.errors import ExternalServiceError
from app.core.observability import get_tracer, tag_exception


_tracer = get_tracer()


class JobsAdapter:
    def __init__(self, ws: WorkspaceClient, logger: Logger):
        self._ws = ws
        self._logger = logger

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

    async def run_and_get_output(
        self,
        job_id: int,
        notebook_params: dict[str, str] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict:
        """Trigger a job, wait for completion, return notebook output as dict."""
        with _tracer.start_as_current_span(
            "dependency.jobs.run",
            attributes={"dependency": "jobs", "operation": "run"},
        ) as span:
            self._logger.info("Triggering job %s", job_id)
            try:
                finished = await run_sync(
                    self._ws.jobs.run_now_and_wait,
                    job_id=job_id,
                    notebook_params=notebook_params or {},
                    error_cls=ExternalServiceError,
                    timeout=timeout,
                )
                last_task_id = finished.tasks[-1].run_id
                out = await run_sync(
                    self._ws.jobs.get_run_output,
                    run_id=last_task_id,
                    error_cls=ExternalServiceError,
                )
                try:
                    result = json.loads(out.notebook_output.result)
                except (json.JSONDecodeError, AttributeError, TypeError) as exc:
                    raise ExternalServiceError(
                        f"Failed to parse job output: {exc}", cause=exc
                    ) from exc
                span.set_attribute("result", "ok")
                return result
            except Exception as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise
