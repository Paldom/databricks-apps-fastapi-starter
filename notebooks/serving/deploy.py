# Databricks notebook source
"""Log, register and serve the ResponsesAgent on a Model Serving endpoint.

Idempotent: re-running logs a new model version and updates the endpoint. The upstream
Foundation Model endpoint is declared as a model resource, so the served model gets
managed credentials for it; nothing is read from a secret scope.
"""

from __future__ import annotations

import time
from pathlib import Path

import mlflow
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from databricks.sdk.service.serving import (
    EndpointCoreConfigInput,
    EndpointStateConfigUpdate,
    EndpointStateReady,
    ServedEntityInput,
)
from mlflow.models.resources import DatabricksServingEndpoint

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
upstream_model = get_param("serving_agent_chat_model")
print({"endpoint": endpoint_name, "model": uc_model_name, "upstream": upstream_model})

mlflow.set_experiment(experiment_id=experiment_id)

# COMMAND ----------

agent_dir = (
    Path("notebooks/serving")
    if Path("notebooks/serving/agent.py").exists()
    else Path(".")
)
agent_file = agent_dir / "agent.py"
pip_requirements = str(agent_dir / "requirements.txt")  # log_model accepts the file path
print(f"Agent file: {agent_file}; requirements: {pip_requirements}")

# COMMAND ----------

with mlflow.start_run(run_name="log-register-serving-agent"):
    model_info = mlflow.pyfunc.log_model(
        name="agent",
        python_model=str(agent_file),
        resources=[DatabricksServingEndpoint(endpoint_name=upstream_model)],
        pip_requirements=pip_requirements,
    )
    print(f"Logged model: {model_info.model_uri}")

registered = mlflow.register_model(
    model_info.model_uri, uc_model_name, await_registration_for=300
)
print(f"Registered: {uc_model_name} v{registered.version}")

# COMMAND ----------

served_entity = ServedEntityInput(
    name="serving-agent",
    entity_name=uc_model_name,
    entity_version=str(registered.version),
    workload_size="Small",
    scale_to_zero_enabled=True,
    environment_vars={
        "ENABLE_MLFLOW_TRACING": "true",
        "MLFLOW_EXPERIMENT_ID": str(experiment_id),
        "SERVING_AGENT_CHAT_MODEL": upstream_model,
    },
)

ws = WorkspaceClient()
try:
    ws.serving_endpoints.get(endpoint_name)
    ws.serving_endpoints.update_config_and_wait(
        name=endpoint_name, served_entities=[served_entity]
    )
    action = "updated"
except NotFound:
    ws.serving_endpoints.create_and_wait(
        name=endpoint_name,
        config=EndpointCoreConfigInput(
            name=endpoint_name, served_entities=[served_entity]
        ),
    )
    action = "created"

# COMMAND ----------

for _ in range(60):  # the waiter returns on the config change; confirm READY
    state = ws.serving_endpoints.get(endpoint_name).state
    if (
        state is not None
        and state.ready == EndpointStateReady.READY
        and state.config_update == EndpointStateConfigUpdate.NOT_UPDATING
    ):
        break
    time.sleep(10)
else:
    raise TimeoutError(f"Endpoint {endpoint_name} did not become READY")

result = {
    "endpoint_name": endpoint_name,
    "uc_model_name": uc_model_name,
    "model_version": registered.version,
    "action": action,
    "state": ready,
}
print(result)
dbutils.notebook.exit(str(result))  # noqa: F821
