# workspace.py
from functools import lru_cache
from databricks.sdk import WorkspaceClient

@lru_cache(maxsize=1)
def w() -> WorkspaceClient:      # singleton
    return WorkspaceClient()