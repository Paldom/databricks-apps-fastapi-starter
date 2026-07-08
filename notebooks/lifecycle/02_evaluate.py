# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Evaluate the serving agent
# MAGIC
# MAGIC Second stop in the lifecycle: score the agent from
# MAGIC `notebooks/serving/agent.py` with `mlflow.genai.evaluate()` — still
# MAGIC in-notebook (fast, cheap, full stack traces), before any deployment.
# MAGIC Three scorers show both scorer families:
# MAGIC - `answer_is_concise` — deterministic `@scorer`, no LLM involved
# MAGIC - `Guidelines` — LLM judge enforcing plain-English rules
# MAGIC - `Safety` — built-in LLM judge for harmful content
# MAGIC
# MAGIC Deployed-surface evals (App / endpoint / Genie) live in `notebooks/evals/`.

# COMMAND ----------

# MAGIC %pip install -U -r ../serving/requirements.txt
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# ── Parameters ──────────────────────────────────────────────────────────────
dbutils.widgets.text("experiment_name", "/Shared/databricks-apps-fastapi-starter/lifecycle")  # noqa: F821
dbutils.widgets.text("serving_agent_chat_model", "databricks-claude-sonnet-4")  # noqa: F821
dbutils.widgets.text("judge_model", "databricks-claude-sonnet-4")  # noqa: F821

EXPERIMENT_NAME = dbutils.widgets.get("experiment_name").strip()  # noqa: F821
CHAT_MODEL = dbutils.widgets.get("serving_agent_chat_model").strip()  # noqa: F821
JUDGE_MODEL = dbutils.widgets.get("judge_model").strip()  # noqa: F821

import os

import mlflow

os.environ["SERVING_AGENT_CHAT_MODEL"] = CHAT_MODEL  # read by agent.py
mlflow.set_tracking_uri("databricks")
mlflow.set_experiment(EXPERIMENT_NAME)

# COMMAND ----------

# ── Load the agent from code (same loader as 01_author_and_trace.py) ────────
import sys
from pathlib import Path

agent_file = Path("../serving/agent.py")
if not agent_file.exists():
    agent_file = Path("notebooks/serving/agent.py")
sys.path.insert(0, str(agent_file.resolve().parent))
from agent import ChatAgent  # noqa: E402

chat_agent = ChatAgent()

# predict_fn receives each row's `inputs` dict UNPACKED as kwargs —
# {"inputs": {"question": ...}} arrives here as predict_fn(question=...).
from mlflow.types.responses import ResponsesAgentRequest  # noqa: E402


def predict_fn(question: str) -> dict:
    request = ResponsesAgentRequest(input=[{"role": "user", "content": question}])
    response = chat_agent.predict(request)
    text = "".join(
        part["text"]
        for item in response.output
        if item.type == "message"
        for part in item.content
        if part.get("type") == "output_text"
    )
    return {"response": text}

# COMMAND ----------

# ── Eval dataset: small and inline on purpose ───────────────────────────────
# Each record needs a nested "inputs" key. Grow this by curating real
# production traces later (see notebooks/evals/README.md).
eval_data = [
    {"inputs": {"question": "What is Unity Catalog? Answer in two sentences."}},
    {"inputs": {"question": "How do Databricks Apps authenticate end users?"}},
    {"inputs": {"question": "When should I use a serving endpoint instead of a job?"}},
    {"inputs": {"question": "Explain what MLflow tracing captures for an agent."}},
    {"inputs": {"question": "Write me a haiku about data lakes."}},  # off-mission
]

# COMMAND ----------

# ── Scorers ─────────────────────────────────────────────────────────────────
from mlflow.entities import Feedback  # noqa: E402
from mlflow.genai.scorers import Guidelines, Safety, scorer  # noqa: E402


@scorer
def answer_is_concise(outputs: dict) -> Feedback:
    """Deterministic: the agent promises concise answers — hold it to that."""
    words = len(outputs.get("response", "").split())
    return Feedback(value="yes" if 0 < words <= 150 else "no", rationale=f"{words} words")


guidelines_judge = Guidelines(
    name="helpful_and_grounded",
    guidelines=[
        "The response must directly address the user's request.",
        "The response must not invent Databricks features that do not exist.",
    ],
    model=f"databricks:/{JUDGE_MODEL}",  # judge model is parameterized
)

# COMMAND ----------

# ── Run the evaluation ──────────────────────────────────────────────────────
# One trace per row is logged to the experiment; scorer feedback is attached
# to each trace, and aggregate metrics land on the run.
with mlflow.start_run(run_name="lifecycle-eval"):
    results = mlflow.genai.evaluate(
        data=eval_data,
        predict_fn=predict_fn,
        scorers=[answer_is_concise, guidelines_judge, Safety()],
    )

print(f"Run ID : {results.run_id}")
for name, value in sorted(results.metrics.items()):
    print(f"{name:40s} {value}")
# Read per-row judge rationales in the run's Traces tab, then iterate on the
# prompt (03_register_prompt.py) and re-run.
