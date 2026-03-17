import json
from logging import Logger

from databricks.sdk import WorkspaceClient

from app.core.databricks._async_bridge import run_sync
from app.core.errors import JobExecutionError
from app.core.observability import get_tracer, tag_exception


_tracer = get_tracer()


class JobsAdapter:
    def __init__(self, ws: WorkspaceClient, logger: Logger):
        self._ws = ws
        self._logger = logger

    async def run_and_get_output(
        self,
        job_id: int,
        notebook_params: dict[str, str] | None = None,
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
                    error_cls=JobExecutionError,
                )
                last_task_id = finished.tasks[-1].run_id
                out = await run_sync(
                    self._ws.jobs.get_run_output,
                    run_id=last_task_id,
                    error_cls=JobExecutionError,
                )
                try:
                    result = json.loads(out.notebook_output.result)
                except (json.JSONDecodeError, AttributeError, TypeError) as exc:
                    raise JobExecutionError(
                        f"Failed to parse job output: {exc}", cause=exc
                    ) from exc
                span.set_attribute("result", "ok")
                return result
            except Exception as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise
