# OTel-native Databricks Apps export (beta)

The Apps runtime can auto-inject `OTEL_*` env vars and stream logs/spans/
metrics to Unity Catalog Delta tables (`otel_logs`, `otel_spans`,
`otel_metrics`) via a Zerobus sidecar — SQL-queryable observability.

- This starter ships with OTLP exporters **off** (`OTEL_*_EXPORTER: none` in
  `databricks.yml`) because no collector runs inside the app container.
- To adopt the beta: remove those three env entries and enable the workspace
  feature; spans/metrics additionally need the `opentelemetry-instrument`
  wrapper (already this app's entry command).
- Caveats at time of writing: region-gated, not for compliance-profile
  workspaces, and MLflow Tracing (already on) remains the agent-plane tool —
  the two are different planes, not alternatives (see DESIGN.md).
