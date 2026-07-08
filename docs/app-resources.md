# Apps env vars & resource bindings

Rules learned the hard way (each one failed a real deploy first):

1. **Empty env values are rejected.** Bundles prune empty variable values, and
   the Apps API refuses env entries without `value`/`valueFrom`. Optional
   settings therefore get an env entry **only when configured** — never a
   placeholder empty string.
2. **Never map `PGHOST`/`PGDATABASE`/`PGUSER` manually.** The Apps runtime
   auto-injects all `PG*` variables from a `database` resource binding. A
   manual `valueFrom: lakebase-db` entry resolves every alias to one field and
   corrupts the connection settings (symptom: `password authentication failed
   for user '<hostname>'`).
3. **Bindings by example** (`resources/app.yml`): `serving_endpoint`
   (CAN_QUERY), `job` (CAN_MANAGE_RUN), `uc_securable` volume (WRITE_VOLUME),
   `database` (CAN_CONNECT_AND_CREATE), `experiment` (CAN_MANAGE). Each
   injects its value via `value_from: <binding-name>` in the app env.
4. **Secrets**: bind a secret scope as an app resource and reference it with
   `valueFrom`; never bake secret values into `databricks.yml`.

```yaml
# app resource (resources/app.yml)        # env wiring (databricks.yml)
- name: my-secret                          - name: MY_SECRET
  secret:                                    value_from: my-secret
    scope: my-scope
    key: my-key
    permission: READ
```
