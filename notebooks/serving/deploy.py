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
from mlflow.models.resources import (
    DatabricksServingEndpoint,
    DatabricksVectorSearchIndex,
)

mlflow.set_tracking_uri("databricks")
mlflow.set_registry_uri("databricks-uc")

# COMMAND ----------

WIDGETS = [
    "serving_agent_endpoint",
    "serving_agent_uc_model_name",
    "serving_agent_experiment_id",
    "serving_agent_chat_model",
    # Optional: enable the knowledge_search tool (empty = plain chat agent).
    "serving_agent_vector_search_index",
    "serving_agent_embedding_model",
]

for name in WIDGETS:
    dbutils.widgets.text(name, "")  # noqa: F821


def get_param(name: str) -> str:
    value = dbutils.widgets.get(name)  # noqa: F821
    if not value:
        raise ValueError(f"Missing required parameter: {name}")
    return value


def get_optional_param(name: str) -> str:
    return dbutils.widgets.get(name)  # noqa: F821


endpoint_name = get_param("serving_agent_endpoint")
uc_model_name = get_param("serving_agent_uc_model_name")
experiment_id = get_param("serving_agent_experiment_id")
serving_agent_chat_model = get_param("serving_agent_chat_model")
vector_search_index = get_optional_param("serving_agent_vector_search_index")
embedding_model = get_optional_param("serving_agent_embedding_model")
# agent.py reads these at import; without them the in-notebook validation
# falls back to its hardcoded defaults instead of the job parameters.
os.environ["SERVING_AGENT_CHAT_MODEL"] = serving_agent_chat_model
if vector_search_index and embedding_model:
    os.environ["VECTOR_SEARCH_INDEX_NAME"] = vector_search_index
    os.environ["AI_GATEWAY_EMBEDDING_MODEL"] = embedding_model
print(f"Endpoint: {endpoint_name}")
print(f"Model: {uc_model_name}")
print(f"Experiment: {experiment_id}")
print(f"Upstream: {serving_agent_chat_model}")
print(f"Knowledge tool: {vector_search_index or '(disabled)'}")

mlflow.set_experiment(experiment_id=experiment_id)

# COMMAND ----------

# Resolve the agent code file path
agent_file = Path("notebooks/serving/agent.py")
if not agent_file.exists():
    agent_file = Path("agent.py")  # fallback for local notebook context

print(f"Agent file: {agent_file}")

# COMMAND ----------

# Declaring the Databricks resources the agent touches is the governance /
# credential hook: Model Serving resolves per-resource credentials at serve
# time instead of the agent hardcoding secrets.
model_resources = [DatabricksServingEndpoint(endpoint_name=serving_agent_chat_model)]
if vector_search_index and embedding_model:
    model_resources.append(
        DatabricksVectorSearchIndex(index_name=vector_search_index)
    )
    model_resources.append(
        DatabricksServingEndpoint(endpoint_name=embedding_model)
    )

with mlflow.start_run(run_name="log-register-serving-agent"):
    model_info = mlflow.pyfunc.log_model(
        name="agent",
        python_model=str(agent_file),
        resources=model_resources,
        input_example={
            "input": [{"role": "user", "content": "What is Databricks?"}]
        },
        pip_requirements=[
            # Unpinned mlflow can produce a container Model Serving can't
            # build — pin to the exact version installed in this notebook.
            f"mlflow[databricks]=={mlflow.__version__}",
            "databricks-openai>=0.6.0",
            "databricks-vectorsearch>=0.75",
            "pydantic>=2,<3",
        ],
    )
    print(f"Logged model: {model_info.model_uri}")

# COMMAND ----------

# Validate locally before registering: load the logged model back and run one
# predict against the upstream FM endpoint (uses the notebook's credentials).
loaded = mlflow.pyfunc.load_model(model_info.model_uri)
validation = loaded.predict(
    {"input": [{"role": "user", "content": "Reply with the single word: pong"}]}
)
assert validation["output"], "Local validation returned no output items"
print(f"Local validation output: {validation['output'][-1]}")

# COMMAND ----------

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
    # Serverless job compute does not export DATABRICKS_HOST; use SDK config.
    "DATABRICKS_HOST": WorkspaceClient().config.host,
    "DATABRICKS_CLIENT_ID": "{{secrets/serving-agent/databricks-client-id}}",
    "DATABRICKS_CLIENT_SECRET": "{{secrets/serving-agent/databricks-client-secret}}",
}
if vector_search_index and embedding_model:
    # Enables the knowledge_search tool inside the container (agent.py
    # degrades to a plain chat agent when these are absent).
    env_vars["VECTOR_SEARCH_INDEX_NAME"] = vector_search_index
    env_vars["AI_GATEWAY_EMBEDDING_MODEL"] = embedding_model

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
