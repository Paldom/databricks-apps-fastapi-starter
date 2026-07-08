# Module template

Copy this folder to `app/modules/<your_module>/` to add an optional capability
(the module mechanism is described in `DESIGN.md`). A module is a vertical
slice: spec + optional API router + optional chat-specialist tool, activated
purely by configuration.

Checklist:

1. Copy the folder; rename; fill in `module.py` (and `controller.py`/`tool.py`
   as needed — delete what you don't use).
2. Add your settings fields to `app/core/config.py` and env vars to
   `databricks.yml` + `backend/env.example`.
3. Register one line in `app/modules/__init__.py`'s `ALL_MODULES`.
4. Databricks resources, if any, go in `resources/modules/<name>.yml`,
   activated by a line in `databricks.yml`'s `include:` list.
5. Add a row to the README capability matrix and a test under
   `tests/modules/<your_module>/`.

Removal is the reverse: one folder, one resource file, one include line, one
`ALL_MODULES` line — `make test` must stay green without it.
