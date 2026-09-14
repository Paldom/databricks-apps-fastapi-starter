# Observability

Two planes, different tools, both stored in Unity Catalog.

## Agent plane: MLflow traces

Every chat turn and every supervisor invocation is an MLflow trace whose root span (`chat.turn`, type `AGENT`)
carries the question, the answer, `user.id`, `session.id` and the token counts; the LangChain autolog adds the
model and tool spans below it. The app experiment (`resources/app_experiment.experiment.yml`) stores traces in
the bundle schema (`trace_location`, table prefix `app_mlflow`), so the app's service principal writes to the
`app_mlflow_*` tables through `uc_securable` bindings. Reading traces (UI, `search_traces`, evaluation) needs a
SQL warehouse; the bundle does not create one.

`MLFLOW_TRACE_ENABLE_OTLP_DUAL_EXPORT=true` keeps traces flowing to the experiment while the platform's OTLP
endpoint is configured; without it MLflow would export only over OTLP.

## Infra plane: app telemetry tables

`telemetry_export_destinations` in the app resource writes OpenTelemetry logs, metrics and spans into
`app_logs`, `app_metrics` and `app_traces` in the bundle schema. The app runs under `opentelemetry-instrument`;
`backend/app/core/observability.py` adds thin manual spans around Databricks calls
(`dependency.<service>.<operation>`) with sanitised attributes.

## Log envelope

Application log lines carry `request_id`, `session_id`, `user_id`, `trace_id` and `span_id`
(`OTEL_PYTHON_LOG_FORMAT` in the bundle; the fields come from request context vars through a handler filter in
`core/logging.py`, installed before migrations run). Uvicorn's access log keeps its own format.

## Where to look

| Question                         | Place                                                               |
| -------------------------------- | ------------------------------------------------------------------- |
| what did the agent do on a turn? | the app experiment in the MLflow UI (filter by session or user)     |
| is the app healthy?              | `GET /api/health` (dependency status without exception text)        |
| what did the app log?            | `databricks apps logs <app>` or `SELECT ... FROM <schema>.app_logs` |
| how did the evaluation score?    | the evals experiment (metrics and per-row assessments)              |
