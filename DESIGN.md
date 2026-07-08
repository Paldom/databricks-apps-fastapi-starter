# DESIGN.md — how this starter stays both small and complete

**Mission.** A production-shaped starter for **Databricks Apps** that (1) a newcomer
understands in one sitting, (2) showcases the platform's capabilities, and (3) is
agentic at every level — app, job, and serving endpoint — on one MLflow
`ResponsesAgent` contract.

## The golden path (always on)

Upload a document → file-arrival **Job** ingests it to Vector Search → the **App**'s
chat (LangGraph supervisor) answers with the knowledge tool → the same agent runs on
a **Serving endpoint** (`ResponsesAgent`) → every call is **MLflow-traced** → an
**eval Job** scores the traces → user feedback posts back to them.

One narrative, every level, one agent contract. Everything else is optional.

## The decision rule for every addition

> Does the golden path break without it? **Yes** → core. **No** → an optional
> module (off or deletable by default), or a `docs/` recipe, or don't add it.
> One way per capability — a second way needs an entry in the duality register below.

## Modules

A capability = one **module**: a self-contained vertical slice that is trivially
removable.

| Piece | Where | Mechanism |
|---|---|---|
| Databricks resources | `resources/modules/<name>.yml` | activated by a line in `databricks.yml`'s `include:` list (DABs has no conditional include — the toggle is comment/uncomment) |
| Backend code | `backend/app/modules/<name>/` | registered at startup only when its settings are present; copy `modules/_template` to start one |
| App env | `databricks.yml` app env | entries exist only when configured (the Apps API rejects empty values — bundles prune them) |
| Frontend | feature folder + route | gated at runtime by `GET /api/capabilities` |
| Docs | README capability matrix | one row: capability → module → default → what it showcases |

**Removal contract:** deleting a module = one code folder + one resource file + one
include line; `make test` stays green. CI enforces this shape by testing with
modules disabled.

## Intentional-duality register

These pairs deliberately show two ways to do the same thing. Each file carries a
banner comment pointing here. Do not "deduplicate" them.

| Capability | Managed / high-level way | DIY / low-level way | Why both |
|---|---|---|---|
| Knowledge / RAG | Agent Bricks Knowledge Assistant endpoint (`chat/tools.py`) | Direct embed + Vector Search index (knowledge-DIY module) | shows the build-vs-buy trade-off |
| Genie | SDK adapter (`agents/adapters/genie_adapter.py`) | Raw REST client (examples module) | shows SDK vs REST API surface |
| Observability | MLflow Tracing → UC (agent/eval plane) | OpenTelemetry spans (infra plane) | different planes, not alternatives |
| Chat memory | Lakebase checkpointer (durable) | In-memory checkpointer (dev) | dev/prod split |

## Do's

- Read settings only in `backend/app/core/config.py`; resources only via bundle
  bindings (`value_from`) — never hardcode IDs.
- `ResponsesAgent` is the one agent contract: implement `predict_stream` first,
  derive `predict`; preserve item-based streaming.
- State goes to Lakebase, heavy compute to Jobs/Serving/SQL — the app stays a thin
  UI/API layer ("thin app, heavy platform").
- Every Databricks call gets an MLflow trace; keep manual OTel spans thin.
- New module? Copy `backend/app/modules/_template`, add its yml, add a matrix row.

## Don'ts

- Don't add a second way to do something without a duality-register entry and
  banner comments in both files.
- Don't put agent/business logic in controllers; don't bypass the settings layer
  with `os.getenv`.
- Keep the README comprehensive (architecture, setup, operations) but put
  narrow deep-dives in `docs/` pages rather than growing sections unboundedly.
- Don't weaken gates to get green (no `|| true`, no deleted tests, no unexplained
  `# type: ignore`/`# noqa`, no lowered coverage floor).
- Don't make a module's absence break startup — modules degrade to "not configured",
  never to a crash.
