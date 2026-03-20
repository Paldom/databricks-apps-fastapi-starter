from functools import lru_cache

from databricks.sdk import WorkspaceClient


@lru_cache(maxsize=1)
def get_workspace_client_singleton() -> WorkspaceClient:
    return WorkspaceClient()
