# Workspace bootstrap & first-deploy troubleshooting

The happy path is `make bootstrap-workspace` (detects a writable catalog,
creates the `/Shared` experiments folder, builds the frontend, and writes
`BUNDLE_VAR_*` overrides to `.bundle-vars.dev.sh`), then:

```bash
source .bundle-vars.dev.sh
databricks bundle deploy -t dev -p <profile>
databricks bundle run  -t dev -p <profile> fastapi_app
```

## What the bootstrap encodes (and why)

| Override | Reason |
|---|---|
| `rag_catalog_name` | Many workspaces have no writable `main` catalog |
| `knowledge_upload_root`, `rag_checkpoint_root`, `rag_*_table_name` | Must match the catalog **and** the dev-mode schema prefix (`dev_<user>_starter_rag`) |
| `serving_agent_uc_model_name` | UC model path for the serving agent, same schema |
| `/Shared/databricks-apps-fastapi-starter` folder | The experiments API does not create parent folders |
| Frontend build | `backend/public` is gitignored but force-included in bundle sync |

## Troubleshooting first deploys (each error was hit on a real deploy)

| Error | Cause / fix |
|---|---|
| `Parent directory does not exist: /Shared/...` | Run the bootstrap (or `databricks workspace mkdirs ...`) |
| `User does not have CREATE CATALOG on Metastore` | Only affects the optional Lakebase→UC catalog registration; the app itself is unaffected. Ask a metastore admin or ignore |
| `Catalog 'main' is not accessible` / `Schema ... does not exist` | Use the bootstrap's catalog/path overrides (dev-prefixed schema!) |
| `Endpoint with name '...' does not exist` on app create | An app binding points at a serving endpoint that doesn't exist yet — check `chat_endpoint_name`; deploy the serving agent before wiring `SERVING_AGENT_ENDPOINT` |
| `Must specify environment variable source using either 'value' or 'valueFrom'` | Empty env values are pruned and rejected — see [app-resources.md](app-resources.md) |
| `permission denied for schema public` (migrations/checkpointer) | Run `make grant-db-access` once after the first deploy — the app needs its own schema (see Settings.pg_app_schema) |
| `password authentication failed for user '<hostname>'` in app logs | Manual `PG*` mappings corrupt the auto-injected database binding — see [app-resources.md](app-resources.md) |
| `Error installing packages` during app build | `backend/requirements.txt` must not contain the project itself — regenerate with `make requirements-export` |
| `GET /` returns 404 | Frontend wasn't built before deploy — bootstrap does this |
| `Responses API passthrough is not supported for model X` | Pick a passthrough-capable upstream for the serving agent (commonly the GPT family; probe with a 3-line `openai` script against `/serving-endpoints`) |
| OTLP `Connection refused` spam in app logs | No collector in the Apps runtime; exporters ship disabled — see [otel-native-apps.md](otel-native-apps.md) |

## Verify a deploy

```bash
databricks apps logs <app-name> -p <profile>          # build + runtime logs
curl -H "Authorization: Bearer $(databricks auth token -p <profile> -o json | jq -r .access_token)" \
  https://<app-url>/api/health/ready                  # expect {"ok":true,"db":true}
curl ... https://<app-url>/api/capabilities           # module/specialist state
```

`db:true` proves Lakebase connectivity and that Alembic migrations ran (they
run automatically on every app start).
