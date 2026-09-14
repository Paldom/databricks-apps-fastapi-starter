# App environment and resource bindings

Everything the app talks to is declared in `resources/fastapi_app.app.yml` as an app resource and arrives as an
environment variable. The app reads them in one place (`backend/app/core/config.py`), never with `os.getenv`
elsewhere, and never hardcodes a name or an id.

## Rules the Apps API enforces

1. **No empty values.** An env entry without `value` or `value_from` is rejected, and so is a binding that
   points at nothing. Optional capabilities therefore live in a target block (`targets.<name>.resources.apps`),
   where lists merge by `name`; the base file keeps them as comments.
2. **`PG*` is injected, never mapped.** A `postgres` binding makes the runtime inject `PGHOST`, `PGPORT`,
   `PGDATABASE`, `PGUSER`, `PGSSLMODE` and `PGAPPNAME`; the password is the app's OAuth token, minted per
   connection. Mapping those names by hand corrupts the connection.
3. **Bindings grant the privilege.** The binding gives the app's service principal the listed permission on the
   resource (and `USE CATALOG`/`USE SCHEMA` on the parents of Unity Catalog securables). What a binding cannot
   express is granted by the `postdeploy` hook: `USE_SCHEMA` and `SELECT` on the bundle schema, because the AI
   Search index only exists after the first ingestion run.
4. **Secret ACLs are scope-wide** and reconciled on every deploy. A target that binds a key also declares
   `READ` for the app's service principal on that scope (see the README's Secrets section).

## Binding kinds

| Kind               | Example in this bundle                                                | Permission               | Injected value          |
| ------------------ | --------------------------------------------------------------------- | ------------------------ | ----------------------- |
| `postgres`         | Lakebase Autoscaling branch + database (`app_db`, `main_database`)    | `CAN_CONNECT_AND_CREATE` | `PG*` variables         |
| `experiment`       | app MLflow experiment                                                 | `CAN_MANAGE`             | experiment id           |
| `job`              | ingestion job (`rag_ingestion_job`)                                   | `CAN_MANAGE_RUN`         | job id                  |
| `uc_securable`     | uploads volume (`WRITE_VOLUME`); four `app_mlflow_*` trace tables     | `WRITE_VOLUME`, `MODIFY` | volume path, table name |
| `serving_endpoint` | supervisor model, embedding model, Knowledge Assistant, serving agent | `CAN_QUERY`              | endpoint name           |
| `genie_space`      | Genie space (`name`, `space_id`)                                      | `CAN_RUN`                | space id                |
| `app`              | another Databricks App used as a specialist                           | `CAN_USE`                | app name                |
| `secret`           | one key of the app secret scope                                       | `READ`                   | the secret value        |
| `sql_warehouse`    | a warehouse (comment only; nothing in the app queries one)            | `CAN_USE`                | warehouse id            |

`value_from: <binding name>` in `config.env` selects what is injected; the binding name is free text.

```yaml
# resources/fastapi_app.app.yml (base) and a target override that switches Genie on
resources:
  - name: genie-space
    genie_space:
      {
        name: '${var.genie_space_id}',
        space_id: '${var.genie_space_id}',
        permission: CAN_RUN,
      }
config:
  env:
    - name: GENIE_SPACE_ID
      value_from: genie-space
```

## App fields in use and in reserve

Set in every target: `compute_size`, `lifecycle.started` (deploy also starts the app), `config.command` and
`config.env`, `telemetry_export_destinations` (logs, metrics and traces into Unity Catalog tables). Set in prod:
`forward_user_access_token` and `user_api_scopes` for on-behalf-of calls. Listed as comments because nothing
here uses them yet: `usage_policy_id` or `budget_policy_id`, `compute_min_instances` and `compute_max_instances`,
`space`, `git_repository` and `git_source` (deploying from Git instead of the bundle's `source_code_path`).

## Verify a binding after a deploy

```bash
databricks apps get fastapi-starter-dev --profile "$DATABRICKS_CONFIG_PROFILE" -o json | jq '.resources[] | {name, permission: (.[keys[0]].permission?)}'
databricks apps get fastapi-starter-dev --profile "$DATABRICKS_CONFIG_PROFILE" -o json | jq -r .service_principal_client_id
```

The second value is the principal that holds every granted privilege; grants that are not bindings show up in
`databricks grants get SCHEMA <catalog>.<schema>`.
