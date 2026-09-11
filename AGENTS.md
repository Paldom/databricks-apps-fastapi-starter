# AGENTS.md

Rules for coding agents (Claude Code, Codex, Cursor, Gemini, Copilot) working in this repository. `CLAUDE.md`
imports this file; `.gemini/settings.json` points Gemini at it; Codex, Cursor and Copilot read it natively.
Hooks and pre-commit entries are bash: on Windows use Git Bash or WSL. Keep it short and specific; anything that must always happen is enforced by hooks,
pre-commit and CI, not by prose.

## What this is

A production template for data and AI apps on **Databricks Apps**: FastAPI backend (Python 3.11, SQLAlchemy async,
Alembic, Pydantic Settings), React 19 + TypeScript + Vite frontend served from `backend/public`, a LangGraph
supervisor that routes to specialist tools (remote Databricks App, Model Serving endpoint, Genie Agent, Knowledge
Assistant or direct AI Search retrieval), Lakebase Postgres for app state, MLflow tracing and evaluation, and
Declarative Automation Bundles (`databricks.yml` + `resources/*.yml`) as the only deployment path.

Principle: **everything is resource-based**. Databricks resources are bound to the app in `resources/app.yml` and
arrive as environment variables. Never hardcode resource names or IDs; never read `os.getenv` outside
`backend/app/core/config.py`.

## Layout

```
backend/app/
  api/            FastAPI controllers, mounted at /api      (may import services)
  services/       business logic                            (may import repositories)
  repositories/   SQLAlchemy persistence, flush-only        (may import models)
  models/         ORM models and DTOs
  core/           config, bootstrap, runtime, deps, db, databricks clients, mlflow, observability, pagination
  chat/           LangGraph supervisor, tools, registry, parts (stream reduction), title generation
  agents/         AgentAdapter contract + app/serving/genie adapters
  middlewares/    auth headers, OBO, security headers, request size
backend/alembic/  migrations (run at app start)
backend/tests/    pytest
frontend/src/     app/ (providers, router), components/, hooks/, lib/assistant/ (NDJSON chat runtime), shared/api/ (Orval client)
notebooks/        jobs (RAG ingestion), evals (MLflow), serving (optional Model Serving agent)
resources/        bundle resources: app, database, unity_catalog, vector_search, compute, evals, experiment, serving_agent
scripts/          postdeploy_grants.sh (bundle hook), setup-agentic.sh
```

Layer rules are enforced by import-linter (`backend/pyproject.toml`): `api → services → repositories → models`, and
`core` never imports `chat` or `agents`.

## Commands

```bash
make setup                 # uv sync, npm ci, pre-commit hooks, agent skills (scripts/setup-agentic.sh)
make dev-db && make migrate-up && make dev
make check                 # offline gate: pre-commit, ruff, mypy, bandit, pytest, frontend build (CI runs the same)
make generate              # export OpenAPI, regenerate the frontend client and env.example (commit the result)
cd backend && uv run pytest -q            # or: uv run ruff check . ; uv run mypy app
cd frontend && npm run lint && npm run typecheck && npx vitest run
databricks bundle validate -t dev --profile "$DATABRICKS_CONFIG_PROFILE"
databricks bundle deploy -t dev --profile "$DATABRICKS_CONFIG_PROFILE"   # one step: builds the frontend, provisions, starts the app
```

- Python deps: `uv add` / `uv add --dev` in `backend/`. Never `pip install`. Commit `uv.lock`.
- Node deps: `npm` in `frontend/`. Commit `package-lock.json`.
- Migrations: `make migrate-new MIGRATION_MESSAGE="..."`; they run automatically at app start.

## Definition of done

A task is done when `make check` passes, the change is covered by a test where behaviour changed, generated files
are regenerated (`make generate`), and `git status` is clean. Never make a gate pass by weakening it: no lowering
coverage thresholds, no new `# type: ignore` / `# noqa` / mypy `disable_error_code` / ruff `ignore` without a
one-line reason, no `continue-on-error`, `|| true`, `--no-verify` or skipped hooks. If a check cannot pass, say
so and stop.

## Guardrails (what runs automatically)

| Layer       | Where                                      | What                                                                                                                                                                                                 |
| ----------- | ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Rules       | this file                                  | context only; can be forgotten under pressure                                                                                                                                                        |
| Agent hooks | `.claude/settings.json` → `.claude/hooks/` | PreToolUse denies `--no-verify`, force-push/main push, bare pip, broad `rm -rf`, non-dev bundle deploys; PostToolUse runs ruff/prettier on the edited file; Stop runs pre-commit over the change set |
| Commit gate | `.pre-commit-config.yaml`                  | ruff, mypy, import-linter, detect-secrets, uv lock check, prettier, eslint, schema checks; tsc + pytest on pre-push                                                                                  |
| CI          | `.github/workflows/`                       | the same config plus tests with coverage and `bundle validate`; the only real gate                                                                                                                   |

Hooks are a convenience for agents, not a security boundary. Committed hooks execute on every contributor's
machine, so changes under `.claude/`, `.agents/`, `.github/` and `resources/` need human review (`CODEOWNERS`).

## Working rules

- Read the code you change end to end before editing; fix root causes in the shared function, not the caller.
- Prefer deleting over adding. No abstractions with one implementation, no config for values that never change.
  Review every feature with the `ponytail-review` skill (over-engineering hunt) before calling it done.
- Databricks CLI calls always carry `--profile "$DATABRICKS_CONFIG_PROFILE"`. From an agent session only the `dev`
  target may be deployed or run; `bundle destroy` and staging/prod deployments are human actions.
- Never print tokens, client secrets or `.env` contents. Never commit `.env`, machine-specific MCP config or a
  secrets baseline that contains a real secret.
- Flag for human review: auth and OBO changes, new dependencies, lockfile changes, migrations, bundle resources.
- Optional integrations must degrade cleanly: routes return 503 with a clear message when a resource is not
  configured; startup never crashes because an optional resource is missing.

## Backend conventions

- Settings: one `Settings` class in `core/config.py`; `backend/env.example` is generated from it (`make generate`).
- Auth: Databricks Apps forward `X-Forwarded-User`/`-Email`; `get_current_user` guards every route that reads or
  writes user data, including chat streaming and agent invocations. Local dev uses the fallback user while `ENVIRONMENT=development` unless
  `ENABLE_LOCAL_DEV_AUTH_FALLBACK=false` (the bundle sets it).
- Databricks clients: use the SDK `WorkspaceClient` and `databricks-openai` / `databricks-langchain` clients that
  refresh OAuth tokens; never build an OpenAI client from a static token.
- Chat: `/api/chat/stream` needs an owned chat id; the backend loads the stored transcript, appends the new user
  message, emits NDJSON events `text-delta`, `tool-call-begin`, `tool-call-delta`, `tool-result`, `heartbeat`,
  `done`, `error`, and stores the assistant message (text + content parts) before `done`. The schema is exported to
  `backend/openapi.yaml` and the frontend client is generated from it. Tools raise `ToolException` with a fixed
  public text; per-tool and per-turn deadlines live in `Settings`. Specialists go through `agents/adapters/*`.
- Identity in tools: never from tool arguments; read `config["configurable"]` (`ChatContext.configurable()`).
  Direct AI Search retrieval filters by the caller's `user_id`; a bound Knowledge Assistant is a shared corpus by design.
- Errors: never send `str(exc)` to clients; log it with the request id and return a generic message plus the
  MLflow trace id.
- Tests: `backend/tests` mock external I/O at the adapter boundary only; never stub hard dependencies
  (`langgraph`, `mlflow`, `sqlalchemy`) with fake modules.

## Frontend conventions

- `frontend/src/lib/assistant/` holds the NDJSON parser, the assistant-ui model adapter and the chat runtime; keep
  the wire contract in sync with `backend/openapi.yaml` (`npm run api:gen` after backend changes).
- Data fetching through the generated Orval client and TanStack Query; no raw `fetch` in components.
- UI: shadcn/ui components under `components/ui`; strings through i18next (`public/locales`); every interactive
  control has an accessible name. Use the `hallmark` skill for visual work.
- Tests: vitest + Testing Library + MSW handlers in `src/mocks`; keep coverage thresholds in `vite.config.ts`.
- Build output goes to `backend/public` (gitignored) and is produced by the bundle `prebuild` script at deploy time.

## Bundle conventions

- One app definition (`resources/app.yml`); target differences are variables (`environment`, `log_level`, `enable_obo`, `enable_docs`,
  `enable_examples`). Optional bindings (Knowledge Assistant, serving agent, Genie, remote app) and their env
  entries live in a target (lists merge by `name`); the Apps API rejects empty env values and empty bindings.
- Jobs run on serverless `environments` (`client: "3"`); Lakebase is an autoscaling project; the AI Search endpoint
  and app telemetry destinations are resources; the app and evals experiments store traces in UC (`trace_location`, immutable once set); `lifecycle.started: true` so deploy also starts the app; `experimental.scripts` holds the `prebuild`
  (frontend) and `postdeploy` (UC grants for the app service principal) hooks.
- The Delta Sync index is created by the ingestion job, not declared (its source table must exist first).
- Validate every target before committing bundle changes: `databricks bundle validate -t dev|staging|prod --profile "$DATABRICKS_CONFIG_PROFILE"`.

## Agent tooling

Skills live in `.agents/skills` (installed by `scripts/setup-agentic.sh` from `skills-lock.json` and the Databricks AI
Dev Kit; per-agent directories are symlinks and are gitignored). MCP servers are configured in `.mcp.json`
(Claude), `.cursor/mcp.json` and `.vscode/mcp.json`; the Databricks MCP server comes from the AI Dev Kit plugin.
