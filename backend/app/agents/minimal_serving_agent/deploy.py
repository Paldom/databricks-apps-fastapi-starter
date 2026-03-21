"""Deploy the minimal serving agent to Databricks Model Serving.

Run this notebook (or script) from a Databricks workspace to:
1. Log the agent as an MLflow PyFunc model
2. Register it in Unity Catalog
3. Print the model URI for serving endpoint creation

Usage:
    # From a Databricks notebook cell:
    %run ./deploy

    # Or as a script (requires Databricks runtime):
    python deploy.py
"""
from __future__ import annotations

import os

import mlflow

from app.agents.minimal_serving_agent.agent import MinimalServingAgent

mlflow.set_registry_uri("databricks-uc")

model_name = os.getenv(
    "SERVING_AGENT_MODEL_NAME",
    "app.default.minimal-serving-specialist",
)

with mlflow.start_run(run_name="minimal-serving-agent") as run:
    model_info = mlflow.pyfunc.log_model(
        python_model=MinimalServingAgent(),
        artifact_path="agent",
        pip_requirements=[
            "mlflow>=2.12",
            "openai>=1.0",
        ],
    )

registered = mlflow.register_model(model_info.model_uri, model_name)
print(f"Registered model: {registered.name} version {registered.version}")
print(f"Model URI: models:/{registered.name}/{registered.version}")
print(
    "\nNext steps:\n"
    "  1. Create a serving endpoint pointing to this model version\n"
    "  2. Set SERVING_SPECIALIST_ENDPOINT=<endpoint-name> in the app config\n"
    "  3. Set CHAT_BACKEND=langgraph_supervisor to enable the supervisor\n"
)
