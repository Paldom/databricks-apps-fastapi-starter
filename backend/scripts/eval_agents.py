#!/usr/bin/env python3
"""Unified evaluation harness for app, serving, and Genie agent backends.

Usage
-----
Single-turn evaluation against a Databricks App::

    python -m scripts.eval_agents --target app --name my-app-name

Single-turn evaluation against a Model Serving endpoint::

    python -m scripts.eval_agents --target endpoint --name serving-agent-dev

Single-turn evaluation against Genie (requires local workspace auth)::

    python -m scripts.eval_agents --target genie --name <space-id>

Multi-turn simulation::

    python -m scripts.eval_agents --target endpoint --name serving-agent-dev --multi-turn

Custom eval data::

    python -m scripts.eval_agents --target app --name my-app --data evals/data/sample_questions.json

Environment
-----------
- ``MLFLOW_TRACKING_URI`` — defaults to ``databricks``
- ``MLFLOW_EXPERIMENT_ID`` — must be set for logging results
- ``DATABRICKS_HOST`` / ``DATABRICKS_TOKEN`` — for workspace auth (or use profiles)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure the backend package is importable when running from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mlflow
from mlflow.genai.scorers import RelevanceToQuery, Safety


# ---------------------------------------------------------------------------
# Predict-fn builders
# ---------------------------------------------------------------------------


def _build_app_predict_fn(app_name: str):
    """Return a predict function that calls a Databricks App via the Responses API."""
    from mlflow.genai import to_predict_fn

    return to_predict_fn(f"apps:/{app_name}")


def _build_endpoint_predict_fn(endpoint_name: str):
    """Return a predict function that calls a Model Serving endpoint."""
    from mlflow.genai import to_predict_fn

    return to_predict_fn(f"endpoints:/{endpoint_name}")


def _build_genie_predict_fn(space_id: str):
    """Return a predict function that calls Genie via the adapter."""
    from databricks.sdk import WorkspaceClient

    from app.agents.adapters.genie_adapter import GenieAdapter
    from app.agents.contracts import ResponsesAgentRequest

    ws = WorkspaceClient()
    adapter = GenieAdapter(ws, space_id)

    def predict_fn(input: list[dict], **context: Any) -> dict:
        request = ResponsesAgentRequest(input=input, custom_inputs=context or {})
        result = asyncio.run(adapter.invoke(request))
        return result.response.model_dump()

    return predict_fn


def _build_local_predict_fn(backend: str):
    """Return a predict function that calls a local adapter (for orchestrator testing)."""
    from openai import AsyncOpenAI

    from app.agents.factory import get_agent_adapter
    from app.agents.contracts import ResponsesAgentRequest
    from app.core.config import settings
    from app.core.integrations import ensure_ai_client, ensure_workspace_client
    from app.core.runtime import AppRuntime

    runtime = AppRuntime()
    ai_client: AsyncOpenAI | None = None
    ws_client = None
    try:
        ai_client = ensure_ai_client(runtime, settings)
    except Exception:
        pass
    try:
        ws_client = ensure_workspace_client(runtime, settings)
    except Exception:
        pass

    adapter = get_agent_adapter(
        backend,
        settings=settings,
        ai_client=ai_client,
        workspace_client=ws_client,
    )
    if adapter is None:
        raise ValueError(f"Backend '{backend}' is not configured locally")

    def predict_fn(input: list[dict], **context: Any) -> dict:
        request = ResponsesAgentRequest(input=input, custom_inputs=context or {})
        result = asyncio.run(adapter.invoke(request))
        return result.response.model_dump()

    return predict_fn


def build_predict_fn(target_type: str, target_name: str | None = None):
    """Dispatch to the right predict-fn builder."""
    if target_type == "app":
        if not target_name:
            raise ValueError("--name is required for app targets")
        return _build_app_predict_fn(target_name)

    if target_type == "endpoint":
        if not target_name:
            raise ValueError("--name is required for endpoint targets")
        return _build_endpoint_predict_fn(target_name)

    if target_type == "genie":
        if not target_name:
            raise ValueError("--name (space ID) is required for genie targets")
        return _build_genie_predict_fn(target_name)

    if target_type == "local":
        backend = target_name or "serving_endpoint"
        return _build_local_predict_fn(backend)

    raise ValueError(f"Unsupported target type: {target_type}")


# ---------------------------------------------------------------------------
# Evaluation modes
# ---------------------------------------------------------------------------


def run_single_turn(predict_fn, data: list[dict] | None = None):
    """Run single-turn evaluation with built-in scorers."""
    if data is None:
        data = [
            {"inputs": {"input": [{"role": "user", "content": "What are the main features of Databricks?"}]}},
            {"inputs": {"input": [{"role": "user", "content": "How do I create a Delta table?"}]}},
            {"inputs": {"input": [{"role": "user", "content": "What is a serving endpoint?"}]}},
        ]

    return mlflow.genai.evaluate(
        data=data,
        predict_fn=predict_fn,
        scorers=[Safety(), RelevanceToQuery()],
    )


def run_multi_turn(predict_fn):
    """Run multi-turn evaluation using ConversationSimulator."""
    from mlflow.genai.simulators import ConversationSimulator

    simulator = ConversationSimulator(
        test_cases=[
            {
                "goal": "Understand how to create and query Delta tables",
                "persona": "A data engineer new to Databricks",
                "context": {"user_id": "eval-user-1"},
            },
            {
                "goal": "Understand revenue trends from the data",
                "persona": "A product manager using natural language queries",
                "context": {"user_id": "eval-user-2"},
            },
        ],
        max_turns=3,
    )

    return mlflow.genai.evaluate(
        data=simulator,
        predict_fn=predict_fn,
        scorers=[Safety()],
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Unified agent evaluation harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--target",
        required=True,
        choices=["app", "endpoint", "genie", "local"],
        help="Backend target type to evaluate",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="App name, endpoint name, Genie space ID, or local backend name",
    )
    parser.add_argument(
        "--multi-turn",
        action="store_true",
        help="Run multi-turn conversation simulation instead of single-turn",
    )
    parser.add_argument(
        "--data",
        default=None,
        help="Path to JSON file with evaluation data (list of {input: [...]} objects)",
    )
    args = parser.parse_args()

    # MLflow setup
    os.environ.setdefault("MLFLOW_TRACKING_URI", "databricks")
    experiment_id = os.getenv("MLFLOW_EXPERIMENT_ID")
    if experiment_id:
        mlflow.set_experiment(experiment_id=experiment_id)
    else:
        print("WARNING: MLFLOW_EXPERIMENT_ID not set; results will go to the default experiment")

    predict_fn = build_predict_fn(args.target, args.name)

    eval_data = None
    if args.data:
        with open(args.data) as f:
            raw = json.load(f)
        eval_data = [{"inputs": item} for item in raw]

    if args.multi_turn:
        print(f"Running multi-turn evaluation against {args.target}/{args.name}...")
        result = run_multi_turn(predict_fn)
    else:
        print(f"Running single-turn evaluation against {args.target}/{args.name}...")
        result = run_single_turn(predict_fn, data=eval_data)

    print("\n=== Evaluation Results ===")
    print(result.tables["eval_results"].to_string())
    print(f"\nResults logged to MLflow experiment: {experiment_id or 'default'}")


if __name__ == "__main__":
    main()
