# Documentation

Deep-dive guides for this starter. The [README](../README.md) covers the
architecture, setup, and day-to-day workflows; these pages go further on
individual topics. The design contract (golden path, module mechanism,
intentional dualities) lives in [`DESIGN.md`](../DESIGN.md), and per-layer
agent/contributor guidance in `backend/AGENTS.md` / `frontend/AGENTS.md`.

| Page | Covers |
|---|---|
| [deployment.md](deployment.md) | Workspace bootstrap internals, database schema grant, first-deploy troubleshooting |
| [modules.md](modules.md) | The optional-capability module mechanism: adding, toggling, removing |
| [app-resources.md](app-resources.md) | Apps env-var rules and resource bindings (incl. hard-won platform gotchas) |
| [lakebase.md](lakebase.md) | Lakebase: app schema, durable chat memory, zero-copy branching |
| [oidc-deploy.md](oidc-deploy.md) | GitHub OIDC workload identity federation for CI deploys |
| [otel-native-apps.md](otel-native-apps.md) | OpenTelemetry-native Apps export to Unity Catalog tables (beta) |
| [load-testing.md](load-testing.md) | Locust performance testing against the app |
