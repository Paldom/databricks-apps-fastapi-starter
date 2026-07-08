# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Author & trace the serving agent
# MAGIC
# MAGIC First stop in the agent lifecycle: run this repo's serving agent
# MAGIC (`notebooks/serving/agent.py`, an MLflow `ResponsesAgent`) **inside this
# MAGIC notebook** — no endpoint, no UC model — and watch MLflow Tracing record
# MAGIC every step. Local invocation is the fastest dev loop: full stack traces,
# MAGIC no deploy wait, no serving cost. Deployment happens later via
# MAGIC `notebooks/serving/deploy.py`; evaluation is next in `02_evaluate.py`.

# COMMAND ----------

# MAGIC %pip install -U -r ../serving/requirements.txt
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# ── Parameters (same widget convention as notebooks/serving/deploy.py) ──────
dbutils.widgets.text("experiment_name", "/Shared/databricks-apps-fastapi-starter/lifecycle")  # noqa: F821
dbutils.widgets.text("serving_agent_chat_model", "databricks-claude-sonnet-4")  # noqa: F821

EXPERIMENT_NAME = dbutils.widgets.get("experiment_name").strip()  # noqa: F821
CHAT_MODEL = dbutils.widgets.get("serving_agent_chat_model").strip()  # noqa: F821

# agent.py reads SERVING_AGENT_CHAT_MODEL when the agent is constructed —
# export it before importing so the widget value wins over the default.
import os

os.environ["SERVING_AGENT_CHAT_MODEL"] = CHAT_MODEL
print(f"experiment = {EXPERIMENT_NAME}")
print(f"upstream   = {CHAT_MODEL}")

# COMMAND ----------

# ── MLflow: every invocation below is traced into this experiment ───────────
import mlflow

mlflow.set_tracking_uri("databricks")
mlflow.set_experiment(EXPERIMENT_NAME)

# COMMAND ----------

# ── Load the agent from code ────────────────────────────────────────────────
# The agent file is a "models from code" module: importing it enables
# mlflow.openai.autolog() and calls mlflow.models.set_model(ChatAgent()).
# We import the class and instantiate directly — the exact object Model
# Serving would run, minus the endpoint.
import sys
from pathlib import Path

agent_file = Path("../serving/agent.py")  # interactive: cwd = notebooks/lifecycle
if not agent_file.exists():
    agent_file = Path("notebooks/serving/agent.py")  # job: cwd = bundle root

sys.path.insert(0, str(agent_file.resolve().parent))
from agent import ChatAgent  # noqa: E402

chat_agent = ChatAgent()
print(f"Loaded {agent_file.resolve()} (upstream model: {chat_agent.model})")

# COMMAND ----------

# ── Single traced invocation ────────────────────────────────────────────────
# ResponsesAgentRequest/Response is the one agent contract used at every
# level of this repo (app, job, serving endpoint) — see DESIGN.md.
from mlflow.types.responses import ResponsesAgentRequest  # noqa: E402

request = ResponsesAgentRequest(
    input=[{"role": "user", "content": "In one sentence, what is a Databricks App?"}]
)
response = chat_agent.predict(request)

for item in response.output:
    if item.type == "message":
        for part in item.content:
            if part.get("type") == "output_text":
                print(part["text"])

# COMMAND ----------

# ── Streaming invocation ────────────────────────────────────────────────────
# predict_stream is the primary implementation (predict derives from it in
# spirit): it yields ResponsesAgentStreamEvent deltas, the same item-based
# stream the app's chat endpoint translates to NDJSON.
request = ResponsesAgentRequest(
    input=[{"role": "user", "content": "Name three Databricks compute options."}]
)
for event in chat_agent.predict_stream(request):
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
print()

# COMMAND ----------

# ── Inspect the traces just produced ────────────────────────────────────────
# Each predict/predict_stream call created one trace: a root AGENT span
# (@mlflow.trace) wrapping a manual LLM span plus autologged OpenAI spans.
traces = mlflow.search_traces(max_results=5)
print(f"Recent traces: {len(traces)}")
display(traces[["trace_id", "state", "execution_duration"]])  # noqa: F821

# COMMAND ----------

# ── Walk the span tree of the most recent trace ─────────────────────────────
# This structure is what the eval scorers in 02_evaluate.py (and the eval
# job in resources/evals.yml) reason over — spans are the ground truth.
trace = mlflow.get_trace(traces.iloc[0]["trace_id"])
print(f"Trace {trace.info.trace_id}: {trace.info.state}, {trace.info.execution_duration} ms")
for span in trace.data.spans:
    indent = "  " if span.parent_id else ""
    print(f"{indent}- [{span.span_type}] {span.name}")
