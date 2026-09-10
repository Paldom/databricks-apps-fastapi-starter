# Databricks notebook source
# MAGIC %md
# MAGIC # Agent Evaluation Helpers
# MAGIC
# MAGIC Reusable wrappers for building predict functions, loading evaluation data,
# MAGIC running evaluations, and persisting artifacts.  Loaded by `run_agent_evals`
# MAGIC via `%run ./_agent_eval_common`.

# COMMAND ----------

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import mlflow

# COMMAND ----------

# ---------------------------------------------------------------------------
# Predict-fn builders
# ---------------------------------------------------------------------------


def build_predict_fn(target_kind: str, target_name: str, secret_scope: str = ""):
    """Return a predict_fn compatible with ``mlflow.genai.evaluate()``."""
    if target_kind == "endpoint":
        return _build_endpoint_predict_fn(target_name)
    if target_kind == "app":
        return _build_app_predict_fn(target_name, secret_scope)
    if target_kind == "genie":
        return _build_genie_predict_fn(target_name)
    raise ValueError(f"Unknown target_kind: {target_kind}")


def _build_endpoint_predict_fn(endpoint_name: str):
    """Use ``mlflow.genai.to_predict_fn()`` — the cleanest path for serving."""
    return mlflow.genai.to_predict_fn(f"endpoints:/{endpoint_name}")


def _app_access_token(ws: Any, secret_scope: str) -> str:
    """An OAuth token the Apps ingress accepts.

    A job's own credential is an internal token that the ingress rejects (401) and that
    cannot be exchanged without an account federation policy. Two ways work:
    - a service principal with CAN_USE on the app whose client id/secret sit in
      ``secret_scope`` (keys ``client-id`` and ``client-secret``): client-credentials flow;
    - outside a job (a machine with ``databricks auth login``): the SDK's OAuth token.
    """
    import requests

    if secret_scope:
        secrets = globals()["dbutils"].secrets
        response = requests.post(
            f"{ws.config.host.rstrip('/')}/oidc/v1/token",
            auth=(
                secrets.get(secret_scope, "client-id"),
                secrets.get(secret_scope, "client-secret"),
            ),
            data={"grant_type": "client_credentials", "scope": "all-apis"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["access_token"]
    if "dbutils" in globals():
        raise RuntimeError(
            "The app target needs a caller the Apps ingress accepts: set eval_secret_scope "
            "(service principal client-id/client-secret with CAN_USE on the app) or run "
            "the app target from a machine with `databricks auth login`."
        )
    return ws.config.oauth_token().access_token


def _build_app_predict_fn(app_name: str, secret_scope: str = ""):
    """Call the app's Responses-compatible supervisor route through the Apps ingress."""
    import requests
    from databricks.sdk import WorkspaceClient
    from mlflow.types.responses import ResponsesAgentResponse

    ws = WorkspaceClient()
    app_url = ws.apps.get(app_name).url.rstrip("/")
    token = _app_access_token(ws, secret_scope)

    def predict_fn(input: list[dict], custom_inputs: dict | None = None, **kwargs):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        response = requests.post(
            f"{app_url}/api/agents/supervisor/invocations",
            headers=headers,
            json={"input": input, "custom_inputs": custom_inputs or {}},
            timeout=120,
            allow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
        meta = payload.pop("_meta", {}) or {}
        normalized = ResponsesAgentResponse(**payload).model_dump()
        normalized.setdefault("custom_outputs", {})["backend"] = "app"
        if meta.get("downstream_trace_id"):
            normalized["custom_outputs"]["downstream_trace_id"] = str(
                meta["downstream_trace_id"]
            )
        return normalized

    return predict_fn


def _build_genie_predict_fn(space_id: str):
    """Query a live Genie space, preserving structured metadata."""
    from databricks.sdk import WorkspaceClient

    ws = WorkspaceClient()

    def predict_fn(input: list[dict], custom_inputs: dict | None = None, **kwargs):
        prompt = _extract_last_user_text(input)
        if not prompt:
            raise ValueError("No user prompt found in input")

        rsp = ws.genie.start_conversation_and_wait(space_id=space_id, content=prompt)

        text, sql, attachments, conversation_id = _parse_genie_response(rsp)

        return {
            "output": [
                {
                    "type": "message",
                    "id": f"msg_{uuid4().hex}",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {"type": "output_text", "text": text, "annotations": []}
                    ],
                }
            ],
            "custom_outputs": {
                "backend": "genie",
                "space_id": space_id,
                "sql": sql,
                "conversation_id": conversation_id,
                "attachments": attachments,
            },
        }

    return predict_fn


def _extract_last_user_text(input_items: list[dict]) -> str:
    """Pull the latest user text from a Responses-style input list."""
    for item in reversed(input_items):
        if item.get("role") != "user":
            continue
        content = item.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in (
                    "input_text",
                    "text",
                ):
                    return block.get("text", "")
                if isinstance(block, str):
                    return block
    return ""


def _parse_genie_response(rsp: Any) -> tuple[str, str | None, list, str | None]:
    """Return (text, sql, attachments, conversation_id) from a Genie response."""
    text_parts: list[str] = []
    sql: str | None = None
    attachments: list[dict] = []

    for att in getattr(rsp, "attachments", []) or []:
        rec: dict[str, Any] = {}
        text_obj = getattr(att, "text", None)
        if text_obj is not None:
            content = getattr(text_obj, "content", None) or str(text_obj)
            rec["type"] = "text"
            rec["text"] = content
            text_parts.append(content)
        query_obj = getattr(att, "query", None)
        if query_obj is not None:
            q = getattr(query_obj, "query", None) or str(query_obj)
            rec["type"] = rec.get("type", "query")
            rec["query"] = q
            if not sql:
                sql = q
            text_parts.append(f"SQL: {q}")
        if rec:
            attachments.append(rec)

    text = "\n\n".join(p for p in text_parts if p).strip() or "No Genie response text"
    return text, sql, attachments, getattr(rsp, "conversation_id", None)


# COMMAND ----------

# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------


def load_eval_data(dataset_name: str, target_kind: str) -> list[dict]:
    """Load an MLflow evaluation dataset or return a small inline fallback."""
    if dataset_name:
        return mlflow.genai.datasets.get_dataset(dataset_name)

    # Small inline fallback; every row carries expectations so Correctness can score it.
    return [
        {
            "inputs": {
                "input": [{"role": "user", "content": "What is MLflow used for?"}]
            },
            "expectations": {
                "expected_facts": [
                    "tracking experiments",
                    "evaluating models or agents",
                ]
            },
        },
        {
            "inputs": {
                "input": [{"role": "user", "content": "What is a Delta table?"}]
            },
            "expectations": {
                "expected_facts": [
                    "a table format on data lake storage",
                    "ACID transactions",
                ]
            },
        },
        {
            "inputs": {
                "input": [
                    {
                        "role": "user",
                        "content": "What does a Model Serving endpoint do?",
                    }
                ]
            },
            "expectations": {
                "expected_facts": ["serves a model over an HTTP endpoint"]
            },
        },
    ]


# COMMAND ----------

# ---------------------------------------------------------------------------
# Evaluation runners
# ---------------------------------------------------------------------------


def run_single_turn_eval(*, predict_fn, data: list[dict], judge_model: str):
    """Single-turn evaluation with explicit built-in scorers and a Foundation Model judge."""
    from mlflow.genai.scorers import Correctness, RelevanceToQuery, Safety

    judge = (
        judge_model
        if judge_model.startswith("databricks:/")
        else f"databricks:/{judge_model}"
    )
    scorers = [
        Correctness(model=judge),  # needs expectations on every row
        Safety(model=judge),
        RelevanceToQuery(model=judge),
    ]

    with mlflow.start_run(run_name="agent-eval-single-turn"):
        return mlflow.genai.evaluate(
            data=data,
            predict_fn=predict_fn,
            scorers=scorers,
        )


def run_multi_turn_eval(*, predict_fn, judge_model: str, max_turns: int = 3):
    """Run multi-turn evaluation using ConversationSimulator (experimental)."""
    from mlflow.genai.scorers import Safety
    from mlflow.genai.simulators import ConversationSimulator

    simulator = ConversationSimulator(
        test_cases=[
            {
                "inputs": {
                    "goal": "Understand revenue trends by region",
                    "persona": "You are a product manager who wants concise answers.",
                }
            },
        ],
        max_turns=max_turns,
    )

    with mlflow.start_run(run_name="agent-eval-multi-turn"):
        return mlflow.genai.evaluate(
            data=simulator,
            predict_fn=predict_fn,
            scorers=[Safety(model=judge_model)],
        )


# COMMAND ----------

# ---------------------------------------------------------------------------
# Artifact persistence
# ---------------------------------------------------------------------------


def log_eval_outputs(
    result,
    *,
    target_kind: str,
    target_name: str,
    eval_mode: str,
) -> dict[str, Any]:
    """Log CSV + JSON artifacts and return a machine-readable summary."""
    summary: dict[str, Any] = {
        "target_kind": target_kind,
        "target_name": target_name,
        "eval_mode": eval_mode,
        "run_id": result.run_id,
        "metrics": result.metrics,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        csv_path = tmp / "evaluation_results.csv"
        json_path = tmp / "evaluation_summary.json"

        result.result_df.to_csv(str(csv_path), index=False)
        json_path.write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8"
        )

        mlflow.log_artifact(str(csv_path), artifact_path="eval")
        mlflow.log_artifact(str(json_path), artifact_path="eval")

    # Set job task values (no-op outside a job run)
    try:
        dbutils.jobs.taskValues.set(key="eval_run_id", value=result.run_id)  # noqa: F821
        dbutils.jobs.taskValues.set(  # noqa: F821
            key="eval_metrics", value=json.dumps(result.metrics, default=str)
        )
    except Exception:
        pass

    return summary
