# Modules: optional capabilities

A *module* is a self-contained vertical slice of one optional capability
(design rationale in [`DESIGN.md`](../DESIGN.md)). Modules keep the core
golden path small while letting the starter showcase many platform features.

## Anatomy

| Piece | Where | Mechanism |
|---|---|---|
| Backend code | `backend/app/modules/<name>/` | `ModuleSpec` in `module.py`; registered in `app/modules/__init__.py` |
| Databricks resources | `resources/modules/<name>.yml` | a line in `databricks.yml`'s `include:` list (comment out to disable) |
| App env vars | `databricks.yml` app env | present only when configured — the Apps API rejects empty values |
| Frontend gating | `GET /api/capabilities` | runtime discovery; no rebuild to hide inactive features |
| Docs | README capability matrix | one row per module |

A module activates when all its `config_keys` (Settings fields) are set. An
inactive module's routes are absent (404) and its chat specialist is not
registered; active modules still guard downstream configuration with 503s.

## Adding a module

1. Copy `backend/app/modules/_template/` and follow its README checklist.
2. Settings fields in `app/core/config.py`; env vars in `databricks.yml` +
   `backend/env.example`.
3. One line in `ALL_MODULES` (`app/modules/__init__.py`).
4. Resources (if any) in `resources/modules/<name>.yml` + an include line.
5. Tests under `backend/tests/modules/<name>/`, a capability-matrix row.

## Removal contract

Deleting a module = one code folder + one resource file + one include line +
one `ALL_MODULES` line; `make test` stays green. If removing your module
breaks anything else, it wasn't a module.

## Shipped modules

| Module | Activation | What it showcases |
|---|---|---|
| `examples` | `ENABLE_DATABRICKS_INTEGRATIONS` | one-call-per-endpoint platform examples (Serving, Jobs, Genie REST, Volumes, SQL warehouse) |
| `knowledge-diy` | embedding + Vector Search settings | DIY RAG (duality with the managed Knowledge Assistant) |
| `supervisor-agent` | `MAS_ENDPOINT` | delegation to an Agent Bricks Multi-Agent Supervisor |
| `cost-guardrail` | include-list toggle | scheduled app stop/start jobs |
