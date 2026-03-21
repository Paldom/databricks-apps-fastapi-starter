"""Minimal serving specialist agent.

This is a sample agent designed to be deployed on Databricks Model Serving.
It demonstrates the simplest possible pattern: one role, one prompt, one model.

Usage:
    1. Log/register the model using the deploy notebook
    2. Deploy as a Databricks Model Serving endpoint
    3. Configure SERVING_SPECIALIST_ENDPOINT in the app to point to it
"""
from __future__ import annotations

import mlflow
from mlflow.models import set_model

SYSTEM_PROMPT = """\
You are a specialised assistant deployed on Databricks Model Serving.
Answer questions accurately and concisely within your domain.
If a question is outside your scope, say so clearly.
"""


class MinimalServingAgent(mlflow.pyfunc.PythonModel):  # type: ignore[name-defined]
    """A minimal MLflow PyFunc model that wraps an LLM call."""

    def predict(self, context, model_input, params=None):
        """Handle a single prediction request.

        ``model_input`` is expected to be a list of dicts with ``role`` and
        ``content`` keys (OpenAI chat message format).
        """
        import openai

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if isinstance(model_input, list):
            messages.extend(model_input)
        elif isinstance(model_input, dict):
            messages.append(model_input)
        else:
            messages.append({"role": "user", "content": str(model_input)})

        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="databricks-meta-llama-3-1-70b-instruct",
            messages=messages,
        )
        return response.choices[0].message.content or ""


set_model(MinimalServingAgent())
