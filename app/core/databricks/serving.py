from logging import Logger

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import DataframeSplitInput

from app.core.databricks._async_bridge import run_sync
from app.core.errors import ServingEndpointError


class ServingAdapter:
    def __init__(self, ws: WorkspaceClient, logger: Logger):
        self._ws = ws
        self._logger = logger

    async def query(
        self,
        endpoint_name: str,
        dataframe_split: dict,
    ) -> dict:
        """Query a model serving endpoint. Returns the response as a dict."""
        df_split = DataframeSplitInput.from_dict(dataframe_split)
        self._logger.info("Querying serving endpoint %s", endpoint_name)
        resp = await run_sync(
            self._ws.serving_endpoints.query,
            name=endpoint_name,
            dataframe_split=df_split,
            error_cls=ServingEndpointError,
        )
        return resp.as_dict()
