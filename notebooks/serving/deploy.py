# Databricks notebook source
# MAGIC %pip install -U -r ./requirements.txt
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

"""Deploy the serving agent to a Databricks Model Serving endpoint.

Idempotent: re-running logs a new model version and updates the endpoint.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import mlflow
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput

mlflow.set_tracking_uri("databricks")
mlflow.set_registry_uri("databricks-uc")

# COMMAND ----------

WIDGETS = [
    "serving_agent_endpoint",
    "serving_agent_uc_model_name",
    "serving_agent_experiment_id",
    "serving_agent_chat_model",
]

for name in WIDGETS:
    dbutils.widgets.text(name, "")  # noqa: F821


def get_param(name: str) -> str:
    value = dbutils.widgets.get(name)  # noqa: F821
    if not value:
        raise ValueError(f"Missing required parameter: {name}")
    return value


endpoint_name = get_param("serving_agent_endpoint")
uc_model_name = get_param("serving_agent_uc_model_name")
experiment_id = get_param("serving_agent_experiment_id")
serving_agent_chat_model = get_param("serving_agent_chat_model")
print(f"Endpoint: {endpoint_name}")
print(f"Model: {uc_model_name}")
print(f"Experiment: {experiment_id}")
print(f"Upstream: {serving_agent_chat_model}")

mlflow.set_experiment(experiment_id=experiment_id)

# COMMAND ----------

# Resolve the agent code file path
agent_file = Path("notebooks/serving/agent.py")
if not agent_file.exists():
    agent_file = Path("agent.py")  # fallback for local notebook context

print(f"Agent file: {agent_file}")

# COMMAND ----------

with mlflow.start_run(run_name="log-register-serving-agent"):
    model_info = mlflow.pyfunc.log_model(
        artifact_path="agent",
        python_model=str(agent_file),
        pip_requirements=[
            f"mlflow[databricks]=={mlflow.__version__}",
            "databricks-openai>=0.6.0",
            "pydantic>=2,<3",
        ],
    )
    print(f"Logged model: {model_info.model_uri}")

registered = mlflow.register_model(model_info.model_uri, uc_model_name)
print(f"Registered: {uc_model_name} v{registered.version}")

# COMMAND ----------

# Wait for model version to become READY
mlflow_client = mlflow.MlflowClient()
for _ in range(60):
    mv = mlflow_client.get_model_version(uc_model_name, registered.version)
    if mv.status == "READY":
        print(f"Model version {registered.version} is READY")
        break
    time.sleep(5)
else:
    raise TimeoutError(
        f"Model version {registered.version} for {uc_model_name} "
        "did not become READY in time."
    )

# COMMAND ----------

env_vars = {
    "ENABLE_MLFLOW_TRACING": "true",
    "MLFLOW_EXPERIMENT_ID": str(experiment_id),
    "SERVING_AGENT_CHAT_MODEL": serving_agent_chat_model,
    "DATABRICKS_HOST": os.environ["DATABRICKS_HOST"],
    "DATABRICKS_CLIENT_ID": "{{secrets/serving-agent/databricks-client-id}}",
    "DATABRICKS_CLIENT_SECRET": "{{secrets/serving-agent/databricks-client-secret}}",
}

served_entity = ServedEntityInput(
    name="serving-agent",
    entity_name=uc_model_name,
    entity_version=registered.version,
    workload_size="Small",
    scale_to_zero_enabled=True,
    environment_vars=env_vars,
)

ws = WorkspaceClient()

try:
    ws.serving_endpoints.get(endpoint_name)
    ws.serving_endpoints.update_config_and_wait(
        name=endpoint_name,
        served_entities=[served_entity],
    )
    action = "updated"
except NotFound:
    ws.serving_endpoints.create_and_wait(
        name=endpoint_name,
        config=EndpointCoreConfigInput(served_entities=[served_entity]),
    )
    action = "created"

# COMMAND ----------

print(
    {
        "endpoint_name": endpoint_name,
        "uc_model_name": uc_model_name,
        "model_version": registered.version,
        "action": action,
    }
)
