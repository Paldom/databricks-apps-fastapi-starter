# Agent evaluations

Evaluations run as a bundle job (`resources/evals.yml`), not as backend code: they target deployed surfaces
(the app, a Model Serving endpoint, a Genie space) through `mlflow.genai.evaluate`.

```
notebooks/evals/
  run_agent_evals.py       entry notebook (parameters below)
  _agent_eval_common.py    predict functions, scorers, dataset loading (%run)
```

The job has one `for_each_task` over the `eval_targets` variable (JSON list of `{kind, name}`; kinds `app`,
`endpoint`, `genie`). Each iteration runs the notebook on serverless compute with:

| Parameter                    | Meaning                                                                                   |
| ---------------------------- | ----------------------------------------------------------------------------------------- |
| `target_kind`, `target_name` | the surface under test                                                                    |
| `eval_experiment_name`       | the evals experiment (traces stored in Unity Catalog)                                     |
| `dataset_name`               | optional UC-backed MLflow dataset; empty uses the inline sample set                       |
| `judge_model`                | Foundation Model endpoint for `Correctness`, `Safety`, `RelevanceToQuery`                 |
| `sql_warehouse_id`           | warehouse used to read UC-stored traces                                                   |
| `eval_secret_scope`          | secret scope with `client-id`/`client-secret` of a service principal that may use the app |
| `fail_on_missing_target`     | `true` by default: an empty target fails the run                                          |

The app target calls `POST /api/agents/supervisor/invocations` through the Apps ingress. A job's own
credential is rejected there, so a job needs `eval_secret_scope`; from a machine with `databricks auth login`
the notebook helpers work with the user's OAuth token. Endpoint targets use `mlflow.genai.to_predict_fn`,
Genie targets the Genie API.

```bash
databricks bundle run -t dev --profile "$DATABRICKS_CONFIG_PROFILE" agent_eval_job
```

Results (metrics, per-row assessments, CSV and JSON artifacts) are in the evals experiment.
