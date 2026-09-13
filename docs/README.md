# Documentation

The [README](../README.md) covers architecture, setup and day-to-day work; these pages go deeper on one topic
each. The design contract (golden path, optional capabilities, dualities) is [`DESIGN.md`](../DESIGN.md);
per-layer agent guidance lives in `backend/AGENTS.md` and `frontend/AGENTS.md`.

| Page                                 | Covers                                                                          |
| ------------------------------------ | ------------------------------------------------------------------------------- |
| [deployment.md](deployment.md)       | What one `bundle deploy` does, target differences, first-deploy troubleshooting |
| [app-resources.md](app-resources.md) | App environment rules and every resource binding kind, with the gotchas         |
| [lakebase.md](lakebase.md)           | Lakebase Autoscaling project, the app-owned schema, migrations, branches        |
| [capabilities.md](capabilities.md)   | Specialists and showcase routes: how a capability is switched on and removed    |
| [agents.md](agents.md)               | The supervisor, the adapters and the NDJSON stream protocol                     |
| [rag.md](rag.md)                     | Upload, the file-arrival ingestion job, the AI Search index, per-user retrieval |
| [evaluation.md](evaluation.md)       | The evaluation job, its targets, credentials and datasets                       |
| [api-client.md](api-client.md)       | The frontend client generated from the backend OpenAPI with Orval               |
| [observability.md](observability.md) | MLflow traces in Unity Catalog, app telemetry tables, the log envelope          |
| [oidc-deploy.md](oidc-deploy.md)     | GitHub deploys with workload identity federation, no client secret              |
| [load-testing.md](load-testing.md)   | Locust runs against a local or deployed app                                     |
