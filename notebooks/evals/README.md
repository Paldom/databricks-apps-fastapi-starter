# MLflow Agent Evaluations

Agent evaluations run as **Databricks notebook/job workflows**, not backend
scripts.  This keeps evaluations at the correct system boundary — they target
deployed surfaces (App, Serving Endpoint, Genie) rather than importing backend
internals.

---

## Architecture

```
notebooks/evals/
  run_agent_evals.py       # Main notebook entrypoint (parameterised)
  _agent_eval_common.py    # Reusable helpers (%run loaded)

resources/evals.yml        # Bundle job + experiment
```

The bundle defines a single job (`AgentEval-{suffix}`) with three tasks — one
per deployed surface.  Each task runs the same notebook with different
parameters.

---

## Running evaluations

### As a bundle job (CI / nightly)

```bash
# Deploy (includes eval job, experiment, etc.)
databricks bundle deploy -t dev

# Run all eval tasks
databricks bundle run -t dev agent_eval_job
```

Tasks that reference an unconfigured target (e.g. empty `genie_space_id`) will
**skip gracefully** by default.  Set `fail_on_missing_target=true` in the job
parameters to fail instead.

### Interactively in a notebook

1. Open `notebooks/evals/run_agent_evals.py` in your workspace.
2. Attach to any cluster with `mlflow[databricks]`, `databricks-openai`, and
   `databricks-sdk` installed.
3. Set widget values (target_kind, target_name, etc.).
4. Run all cells.

This is the recommended path for iterative development and debugging.

---

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `target_kind` | `app`, `endpoint`, `genie` | `endpoint` | Which deployed surface to evaluate |
| `target_name` | string | *(required)* | App name, endpoint name, or Genie space ID |
| `eval_mode` | `single_turn`, `multi_turn` | `single_turn` | Evaluation mode |
| `eval_experiment_name` | MLflow path | `/Shared/.../evals` | Experiment for eval runs |
| `dataset_name` | string | *(empty → inline)* | UC-backed MLflow dataset name |
| `judge_model` | string | `databricks-claude-sonnet-4` | LLM judge for scorers |
| `max_turns` | int | `3` | Max turns for multi-turn mode |
| `fail_on_missing_target` | `true`, `false` | `false` | Fail if target is empty |

---

## Target types

### Model Serving endpoint (`endpoint`)

Uses `mlflow.genai.to_predict_fn("endpoints:/<name>")` — the cleanest
evaluation path.  Assumes the endpoint serves a `ResponsesAgent`.

### Databricks App (`app`)

Queries the deployed app remotely via `DatabricksOpenAI` + Responses API.
Requests downstream MLflow trace IDs via `x-mlflow-return-trace-id` header.

Does **not** import backend code.

### Genie (`genie`)

Calls the live Genie space via the Databricks SDK.  Preserves SQL,
attachments, conversation IDs, and provenance in `custom_outputs`.

Genie does not currently provide MLflow trace IDs.

---

## Artifacts

Each evaluation run logs:

| Artifact | Description |
|----------|-------------|
| `eval/evaluation_results.csv` | Per-example scores and predictions |
| `eval/evaluation_summary.json` | Machine-readable summary (target, metrics, run_id) |
| MLflow metrics | Aggregated scorer metrics |
| Job task values | `eval_run_id`, `eval_metrics` (when running as a job) |

The notebook exits with `dbutils.notebook.exit(json.dumps(summary))` for
downstream task orchestration.

---

## Permissions

The eval job's run identity must be able to:

- **Query** the deployed serving endpoint
- **Access** the deployed Databricks App
- **Run** the Genie space (if evaluating Genie)
- **Write** to the evaluation MLflow experiment
- **Read** any UC-backed evaluation dataset

If using service principal auth, grant these permissions via Unity Catalog and
the bundle's resource permissions.

---

## Multi-turn evaluation (experimental)

Set `eval_mode=multi_turn` to use `ConversationSimulator`.  This is more
volatile than single-turn and uses a small set of hardcoded test cases in
`_agent_eval_common.py`.

For production use, prefer single-turn evaluation with curated datasets.

---

## Creating evaluation datasets

### From traces

Use the MLflow UI or API to select traces and create a UC-backed dataset:

```python
import mlflow

# Select traces from the app experiment
traces = mlflow.search_traces(experiment_ids=["<id>"], filter_string="status = 'OK'")

# Create a dataset from selected traces
mlflow.genai.datasets.create_dataset(
    name="my-eval-dataset",
    data=traces,
)
```

### From curated examples

Create a JSON file and upload it as a dataset:

```python
import mlflow

data = [
    {"inputs": {"input": [{"role": "user", "content": "What is Delta Lake?"}]}},
    {"inputs": {"input": [{"role": "user", "content": "How do I use MLflow?"}]}},
]

mlflow.genai.datasets.create_dataset(name="curated-eval-set", data=data)
```

Then pass `dataset_name=curated-eval-set` to the notebook.
