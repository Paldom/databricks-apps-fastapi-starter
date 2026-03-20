from logging import Logger

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import DataframeSplitInput

from app.core.databricks._async_bridge import run_sync
from app.core.errors import ExternalServiceError
from app.core.observability import get_tracer, safe_attr, tag_exception


_tracer = get_tracer()


class ServingAdapter:
    def __init__(self, ws: WorkspaceClient, logger: Logger):
        self._ws = ws
        self._logger = logger

    async def query(
        self,
        endpoint_name: str,
        dataframe_split: dict,
        *,
        timeout: float | None = None,
    ) -> dict:
        """Query a model serving endpoint. Returns the response as a dict."""
        with _tracer.start_as_current_span(
            "dependency.serving.query",
            attributes={
                "dependency": "serving",
                "operation": "query",
                "serving.endpoint": safe_attr(endpoint_name),
            },
        ) as span:
            df_split = DataframeSplitInput.from_dict(dataframe_split)
            self._logger.info("Querying serving endpoint %s", endpoint_name)
            try:
                resp = await run_sync(
                    self._ws.serving_endpoints.query,
                    name=endpoint_name,
                    dataframe_split=df_split,
                    error_cls=ExternalServiceError,
                    timeout=timeout,
                )
                span.set_attribute("result", "ok")
                return resp.as_dict()
            except Exception as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise
