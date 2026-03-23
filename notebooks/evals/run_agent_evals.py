# Databricks notebook source
# MAGIC %md
# MAGIC # Agent Evaluation Runner
# MAGIC
# MAGIC Evaluates deployed agent surfaces (App, Model Serving, Genie) using MLflow
# MAGIC GenAI evaluation.  Designed to run interactively in a notebook **or** as a
# MAGIC bundle-managed Lakeflow Job task.
# MAGIC
# MAGIC **Parameters** (set via widgets or job base_parameters):
# MAGIC
# MAGIC | Parameter | Description |
# MAGIC |-----------|-------------|
# MAGIC | `target_kind` | `app`, `endpoint`, or `genie` |
# MAGIC | `target_name` | App name, endpoint name, or Genie space ID |
# MAGIC | `eval_mode` | `single_turn` (default) or `multi_turn` |
# MAGIC | `eval_experiment_name` | MLflow experiment path |
# MAGIC | `dataset_name` | Optional UC-backed MLflow dataset name |
# MAGIC | `judge_model` | LLM judge for scorers |
# MAGIC | `max_turns` | Max conversation turns for multi-turn mode |
# MAGIC | `fail_on_missing_target` | `true` to fail if target is unconfigured |

# COMMAND ----------

# MAGIC %pip install -q mlflow[databricks]>=3.1.0 databricks-openai databricks-sdk
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

from __future__ import annotations

import json
import mlflow

# COMMAND ----------

# ── Parameters ────────────────────────────────────────────────────────────

dbutils.widgets.dropdown("target_kind", "endpoint", ["app", "endpoint", "genie"])  # noqa: F821
dbutils.widgets.text("target_name", "")  # noqa: F821
dbutils.widgets.dropdown("eval_mode", "single_turn", ["single_turn", "multi_turn"])  # noqa: F821
dbutils.widgets.text("eval_experiment_name", "/Shared/databricks-apps-fastapi-starter/evals")  # noqa: F821
dbutils.widgets.text("dataset_name", "")  # noqa: F821
dbutils.widgets.text("judge_model", "databricks-claude-sonnet-4")  # noqa: F821
dbutils.widgets.text("max_turns", "3")  # noqa: F821
dbutils.widgets.dropdown("fail_on_missing_target", "false", ["true", "false"])  # noqa: F821

TARGET_KIND = dbutils.widgets.get("target_kind")  # noqa: F821
TARGET_NAME = dbutils.widgets.get("target_name").strip()  # noqa: F821
EVAL_MODE = dbutils.widgets.get("eval_mode")  # noqa: F821
EXPERIMENT_NAME = dbutils.widgets.get("eval_experiment_name").strip()  # noqa: F821
DATASET_NAME = dbutils.widgets.get("dataset_name").strip()  # noqa: F821
JUDGE_MODEL = dbutils.widgets.get("judge_model").strip()  # noqa: F821
MAX_TURNS = int(dbutils.widgets.get("max_turns") or "3")  # noqa: F821
FAIL_ON_MISSING = dbutils.widgets.get("fail_on_missing_target") == "true"  # noqa: F821

print(f"target_kind  = {TARGET_KIND}")
print(f"target_name  = {TARGET_NAME}")
print(f"eval_mode    = {EVAL_MODE}")
print(f"experiment   = {EXPERIMENT_NAME}")
print(f"dataset      = {DATASET_NAME or '(inline fallback)'}")
print(f"judge_model  = {JUDGE_MODEL}")
print(f"max_turns    = {MAX_TURNS}")
print(f"fail_missing = {FAIL_ON_MISSING}")

# COMMAND ----------

# ── MLflow experiment ─────────────────────────────────────────────────────

mlflow.set_tracking_uri("databricks")
mlflow.set_experiment(EXPERIMENT_NAME)
print(f"MLflow experiment: {EXPERIMENT_NAME}")

# COMMAND ----------

# MAGIC %run ./_agent_eval_common

# COMMAND ----------

# ── Validate target ───────────────────────────────────────────────────────

if not TARGET_NAME:
    msg = f"target_name is empty for target_kind={TARGET_KIND}"
    if FAIL_ON_MISSING:
        raise ValueError(msg)
    summary = {
        "target_kind": TARGET_KIND,
        "target_name": "",
        "eval_mode": EVAL_MODE,
        "status": "skipped",
        "reason": msg,
    }
    print(f"SKIPPED: {msg}")
    dbutils.notebook.exit(json.dumps(summary))  # noqa: F821

# COMMAND ----------

# ── Build predict function ────────────────────────────────────────────────

predict_fn = build_predict_fn(target_kind=TARGET_KIND, target_name=TARGET_NAME)  # noqa: F821
print(f"predict_fn ready for {TARGET_KIND}/{TARGET_NAME}")

# COMMAND ----------

# ── Load evaluation data ──────────────────────────────────────────────────

data = load_eval_data(dataset_name=DATASET_NAME, target_kind=TARGET_KIND)  # noqa: F821
print(f"Evaluation data: {len(data)} examples")

# COMMAND ----------

# ── Run evaluation ────────────────────────────────────────────────────────

if EVAL_MODE == "multi_turn":
    print("Running multi-turn evaluation (experimental)...")
    result = run_multi_turn_eval(  # noqa: F821
        predict_fn=predict_fn,
        judge_model=JUDGE_MODEL,
        max_turns=MAX_TURNS,
    )
else:
    print("Running single-turn evaluation...")
    result = run_single_turn_eval(  # noqa: F821
        predict_fn=predict_fn,
        data=data,
        judge_model=JUDGE_MODEL,
    )

# COMMAND ----------

# ── Persist artifacts & exit ──────────────────────────────────────────────

summary = log_eval_outputs(  # noqa: F821
    result,
    target_kind=TARGET_KIND,
    target_name=TARGET_NAME,
    eval_mode=EVAL_MODE,
)

print("\n=== Evaluation Summary ===")
print(json.dumps(summary, indent=2, default=str))

# COMMAND ----------

# ── Show results ──────────────────────────────────────────────────────────

display(result.result_df)  # noqa: F821

# COMMAND ----------

dbutils.notebook.exit(json.dumps(summary, default=str))  # noqa: F821
