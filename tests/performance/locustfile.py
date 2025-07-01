"""
Locust load test for Databricks Apps FastAPI starter.

Usage (local):
  export HOST=https://dbc-123.cloud.databricks.com
  export DATABRICKS_HOST=dbc-123.cloud.databricks.com
  export DATABRICKS_CLIENT_ID=... 
  export DATABRICKS_CLIENT_SECRET=...
  poetry run locust -f tests/performance/locustfile.py --headless -u 50 -r 10 -t 2m
"""

import os
from databricks.sdk import WorkspaceClient
from locust import HttpUser, task, between

class DatabricksAppsUser(HttpUser):
    host = os.getenv("HOST", "http://localhost:8000")
    wait_time = between(1, 3)

    def on_start(self):
        ws = WorkspaceClient(
            host=f"https://{os.getenv('DATABRICKS_HOST', 'localhost')}",
            client_id=os.getenv("DATABRICKS_CLIENT_ID", ""),
            client_secret=os.getenv("DATABRICKS_CLIENT_SECRET", ""),
        )
        self.headers = ws.config.authenticate()

    # ---- tasks ------------------------------------------------------------
    @task(2)
    def healthcheck(self):
        self.client.get("/health/ready", headers=self.headers)

    @task(1)
    def list_todos(self):
        self.client.get("/v1/todo", headers=self.headers)
