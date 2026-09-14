# DESIGN.md: how this starter stays small and complete

**Mission.** A production-shaped starter for **Databricks Apps** that a newcomer understands in one sitting,
shows what the platform can do, and is agentic on every level (app, Lakeflow Job, Model Serving endpoint) on one
MLflow `ResponsesAgent` contract.

## The golden path (always on)

Upload a document → the file-arrival **Lakeflow Job** parses and chunks it and syncs an **AI Search** index →
the **App**'s chat (a LangGraph supervisor) answers with the knowledge specialist, filtered by the uploading
user → every turn is an **MLflow trace** stored in **Unity Catalog** → the **evaluation Job** scores the app,
a Model Serving endpoint or a Genie space with Foundation Model judges. The optional **Model Serving**
`ResponsesAgent` (`notebooks/serving`) shows the same contract on an endpoint; it proxies a chat model and has
no retrieval of its own.

One narrative, every level, one agent contract. Everything else is optional.

## The decision rule for every addition

> Does the golden path break without it? **Yes**: core. **No**: an optional capability (a target-level binding
> plus an adapter, off by default), a `docs/` page, or nothing. One way per capability; a second way needs a row
> in the duality register below.

## Everything is a resource

Declarative Automation Bundles are the only deployment path. `databricks.yml` holds variables and targets; each
Databricks resource lives in its own `resources/<key>.<type>.yml`; the app binds what it uses (Lakebase,
experiment, job, volume, trace tables, model endpoints, secrets) and reads the injected environment variables in
one place, `backend/app/core/config.py`. Nothing hardcodes a name or an id; nothing is created by hand.

## Optional capabilities

| Capability            | Switch                                            | Code                                     |
| --------------------- | ------------------------------------------------- | ---------------------------------------- |
| Genie specialist      | `genie-space` binding + `GENIE_SPACE_ID`          | `agents/adapters/genie_adapter.py`       |
| Knowledge Assistant   | `knowledge-assistant` binding + endpoint env      | `core/databricks/knowledge_assistant.py` |
| Serving agent         | `deploy_serving_agent` job, then the binding      | `notebooks/serving`, `agents/adapters`   |
| Remote app specialist | `app-agent` binding + `APP_AGENT_NAME`            | `agents/adapters/app_adapter.py`         |
| Bound secret          | `app-secret` binding + `EXAMPLE_SECRET`           | `api/examples_controller.py`             |
| Showcase routes       | `ENABLE_EXAMPLES=true` (dev target)               | `api/examples_controller.py`             |
| On-behalf-of          | `ENABLE_OBO`, `forward_user_access_token`, scopes | `middlewares/workspace_client.py`        |

A capability that is not configured degrades to "not configured" (503 with a clear message, or an unregistered
specialist); it never breaks startup. Bindings are target-level because the Apps API rejects empty values.

## Intentional-duality register

| Capability    | Managed way                                          | Direct way                                        | Why both                      |
| ------------- | ---------------------------------------------------- | ------------------------------------------------- | ----------------------------- |
| Knowledge     | Agent Bricks Knowledge Assistant endpoint            | Ingestion job + AI Search index, per-user filter  | build versus buy              |
| Model logic   | Model Serving `ResponsesAgent` (`notebooks/serving`) | In-app LangGraph supervisor                       | endpoint versus app hosting   |
| Observability | MLflow Tracing in Unity Catalog (agent plane)        | OpenTelemetry to the app telemetry tables (infra) | different planes, not options |
| Evaluation    | `mlflow.genai.evaluate` job over deployed surfaces   | `POST /api/agents/{backend}/invocations` by hand  | scheduled versus ad hoc       |

## Do's

- Read settings only in `core/config.py`; bind resources, never hardcode names.
- Keep the app thin: state in Lakebase, heavy compute in Jobs, Serving and SQL.
- Persist the transcript server-side and replay it per turn; there is no LangGraph checkpointer.
- Give every Databricks call a span and every turn an MLflow trace with user and session metadata.
- One resource per bundle file; validate strictly; deploy `dev` from a branch, staging and prod by hand.

## Don'ts

- No second way without a duality row; no abstraction with one implementation.
- No agent logic in controllers; no `os.getenv` outside the settings layer.
- No weakened gate (no `|| true`, deleted test, lowered threshold, unexplained `noqa`).
- No secret value in the bundle; scopes are resources, values are put once with the CLI.
