# Evaluation

`resources/agent_eval_job.job.yml` runs `notebooks/evals/run_agent_evals.py` once per target in the
`eval_targets` variable (a JSON list of `{kind, name}`; kinds `app`, `endpoint`, `genie`) on serverless compute,
with `mlflow.genai.evaluate` and the `Correctness`, `Safety` and `RelevanceToQuery` scorers judged by the
`judge_model` Foundation Model endpoint. Results and per-row assessments land in the evals experiment, whose
traces are stored in Unity Catalog (`evals_mlflow_*`).

```bash
databricks bundle run -t dev --profile "$DATABRICKS_CONFIG_PROFILE" agent_eval_job
```

Requirements: `sql_warehouse_id` (traces in Unity Catalog are read through a warehouse; the job fails early
without one) and, for the `app` target, the `client-id` and `client-secret` keys of a service principal with
`CAN_USE` on the app in the evaluation secret scope, because the Apps ingress rejects a job's own credential.
Endpoint and Genie targets work with the job identity. From a machine with `databricks auth login` the notebook
helpers call the app with the user's own token.

The dataset is the inline sample set unless `agent_eval_dataset_name` names a Unity Catalog MLflow dataset
(which needs the `databricks-agents` package, declared in the job environment). Details of the notebook
parameters: `notebooks/evals/README.md`.
