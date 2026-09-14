---
name: python-lint
description: Sets up and tunes Ruff linting and formatting for a Python package — pyproject [tool.ruff] rule selection, Black/Flake8/isort migration — and fixes lint or format failures. Use when the user says 'set up linting', 'add ruff', 'fix lint errors', 'configure the formatter'. Not for type errors, non-Python file formatting, pre-commit wiring, or CI workflows.
license: MIT
---

# python-lint

## Purpose

Configure Ruff as the single linter and formatter for a Python package — replacing
Black, Flake8 (+ plugins), isort, and pyupgrade — with an explicit rule set in
`pyproject.toml`, then drive `ruff check` and `ruff format --check` to a clean exit.
Covers fresh setup, migration from the legacy stack, rule tuning, and fixing lint or
format failures. Every command below runs in the user's package repository.

## When NOT to use

- **Type errors / mypy / pyright / ty** — Ruff performs no type inference; `ANN`
  rules only police annotation *style*. The python-typing skill, if installed,
  owns this.
- **Pre-commit wiring** (`.pre-commit-config.yaml`, hook rev pinning, staged-file
  runs) — the python-precommit skill. This skill only defines what Ruff should do.
- **CI workflow YAML** (GitHub Actions jobs, matrices, caching) — the python-ci
  skill. This skill supplies the commands a CI job should run, not the workflow.
- **Formatting YAML / JSON / TOML / Markdown prose** — Ruff formats Python
  (including, since 0.16, Python code fences inside Markdown) and nothing else,
  by deliberate maintainer decision
  ([astral-sh/ruff#10738](https://github.com/astral-sh/ruff/issues/10738));
  the python-precommit skill covers non-Python files.
- **Running Ruff automatically on agent edits** (Claude Code hooks) — the
  agent-guardrails skill.

## Workflow

### 1. Inspect before touching anything

```bash
ls .flake8 .isort.cfg setup.cfg tox.ini ruff.toml .ruff.toml 2>/dev/null
grep -nE '^\[tool\.(ruff|black|isort)|^\[flake8\]|^\[isort\]' pyproject.toml setup.cfg tox.ini 2>/dev/null
grep -n 'requires-python' pyproject.toml
```

Pick the path: fresh setup (steps 2–3), migration off Black/Flake8/isort (step 5),
tuning an existing config (step 4), or fixing a red lint gate (step 6).

### 2. Install a pinned Ruff

```bash
uv add --dev "ruff==0.16.6"        # example pin — check the latest release and pin that
# one-off, no project change:
uvx --from 'ruff==0.16.6' ruff check .
```

No-uv fallback (once, applies to every command below): `python -m pip install
'ruff==0.16.6'` and drop the `uv run` prefix.

Why pin — formatter output and the rule catalog change between minor releases:
0.15 shipped a "2026 style guide" that changed lambda and empty-line formatting
([astral.sh/blog/ruff-v0.15.0](https://astral.sh/blog/ruff-v0.15.0)), and 0.16
(2026-07-23) grew the **default** rule set from 59 to 413 rules while dropping 18
`E`/`F` codes from it, so an unconfigured repo's findings changed overnight
([astral.sh/blog/ruff-v0.16.0](https://astral.sh/blog/ruff-v0.16.0)). An unpinned
Ruff makes local, teammate, and CI runs disagree — the top reported lint-workflow
failure. Optionally enforce the pin in config with
`required-version = "0.16.6"` under `[tool.ruff]`. Note that `uv format`
(experimental since uv 0.8.13) runs a Ruff it bundles itself, so its version can
differ from the project's pin — keep `ruff` in dev dependencies as the source of
truth and treat `uv format` as a convenience wrapper.

### 3. Write the config (fresh setup)

All Ruff config lives in `pyproject.toml`. Keep exactly one config file — a
`ruff.toml` next to a `[tool.ruff]` section is a recipe for confusion. Starter:

```toml
[tool.ruff]
target-version = "py311"          # lowest Python you support; gates UP rewrites
line-length = 88
extend-exclude = ["migrations"]   # generated code, if any

[tool.ruff.lint]
select = [
    "E", "W",   # pycodestyle
    "F",        # pyflakes
    "I",        # isort (import sorting)
    "UP",       # pyupgrade
    "B",        # flake8-bugbear
    "C4",       # flake8-comprehensions
    "SIM",      # flake8-simplify
    "RUF",      # Ruff-specific rules
]
ignore = ["E501"]                 # line length is the formatter's job

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101"]        # assert is fine in tests (relevant once S is on)
"__init__.py" = ["F401"]          # re-exports

[tool.ruff.lint.isort]
known-first-party = ["yourpackage"]

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true      # formats Python snippets inside docstrings
```

Non-obvious decisions baked into this block:

- **Never rely on Ruff's default rule set.** Before 0.16 it was `E4`/`E7`/`E9`
  + `F` (59 rules, less than a Flake8+plugins stack); since 0.16 it is 413 rules across
  `B`, `UP`, `SIM`, `PL` and more, with 18 former `E`/`F` defaults removed — a repo
  without `select` gets a different gate on every upgrade. `select` **replaces**
  the default set, so an explicit list freezes it; `select = ["E4", "E7", "E9",
  "F"]` reproduces the pre-0.16 baseline if a team wants exactly that.
- **`ignore = ["E501"]` whenever the formatter is enabled** — `ruff format` already
  wraps at `line-length`; linting it too double-reports on lines the formatter
  cannot break (URLs, long strings).
- **`target-version` gates `UP` (pyupgrade) rewrites.** If unset, Ruff falls back
  to `project.requires-python`; if that is also absent it assumes py310, and
  autofixes can emit syntax that crashes older supported runtimes.
- Avoid `select = ["ALL"]` — it silently enables every new rule on every Ruff
  upgrade, breaking checks unpredictably. Official guidance is to start narrow and
  grow one category at a time
  ([docs.astral.sh/ruff/linter/](https://docs.astral.sh/ruff/linter/)).

Deeper rule catalog, tier strategy, and sub-table options (isort, pydocstyle,
bugbear): `references/rule-selection.md`.

### 4. Tune an existing config

- Noise in one area (tests, scripts, notebooks) → scope it with
  `[tool.ruff.lint.per-file-ignores]`; never delete the rule from `select` globally
  because tests complain. Common: `"tests/**/*.py" = ["S101", "PLR2004"]`,
  `"scripts/*" = ["T201"]`.
- A single intentional violation → `# noqa: <CODE>` with the specific code and a
  short reason. Bare `# noqa` hides every rule on the line.
- Codes from non-Ruff tools in `# noqa` comments (custom Flake8 plugin) →
  declare `external = ["XX"]` in `[tool.ruff.lint]`, or `RUF100` strips those
  comments on the next `--fix`.
- Widen coverage one prefix at a time (`"S"`, `"PT"`, `"PTH"`, …), run
  `uv run ruff check .` after each addition, and fix or scope before adding more.
- Sanity-check the result: `python3 "${CLAUDE_SKILL_DIR}/scripts/check_ruff_config.py" --root .`
  (read-only; flags E501 double-reporting, `ALL`, formatter-conflicting rules,
  leftover legacy configs, missing target-version).

### 5. Migrate from Black / Flake8 / isort

Full mapping tables (commands, config keys, Flake8-plugin→prefix) and the
large-legacy-codebase strategy: `references/migration.md`. The sequence:

1. **Translate config first.** `[tool.black]` → `[tool.ruff]` + `[tool.ruff.format]`,
   `[tool.isort]`/`.isort.cfg` → `[tool.ruff.lint.isort]` (kebab-case keys),
   `.flake8` → `select`/`ignore`/`per-file-ignores`. Ruff never reads
   `[tool.black]` or `.flake8` — anything not translated is silently lost.
2. **Check plugin parity.** For each Flake8 plugin in use, confirm a Ruff prefix
   exists (table in the reference). A business-critical plugin with no equivalent
   → hybrid: keep Flake8 scoped to that plugin, add its codes to
   `external = [...]`.
3. **One-time cleanup as its own reviewed commit**, before any gate is switched:
   ```bash
   uv run ruff check . --fix && uv run ruff format .
   ```
   Review the diff — Ruff's formatter is close to Black on large codebases but not
   byte-identical; deviations are documented at
   [docs.astral.sh/ruff/formatter/black/](https://docs.astral.sh/ruff/formatter/black/).
   For a large reformat, record the commit in `.git-blame-ignore-revs`.
4. **Retire the old stack in the same PR**: remove black/flake8/isort (and their
   plugins) from dev dependencies; delete `.flake8`, `.isort.cfg`, `[tool.black]`,
   `[tool.isort]`. Two active formatters will fight over the same lines
   ([astral-sh/ruff#1307](https://github.com/astral-sh/ruff/issues/1307)).
5. **Tell the user to repoint whatever invoked the old tools** — pre-commit hooks
   (python-precommit skill) and CI jobs (python-ci skill). Provide only the
   commands: `ruff check .` and `ruff format --check .`.

An existing Black+Flake8 setup that works and hurts nobody is a valid reason to
not migrate — churn has cost. Migrate when there is friction (speed, config
sprawl, plugin abandonment), not for fashion.

### 6. Fix lint / format failures

```bash
uv run ruff check . --fix    # 1. autofix what's safe
uv run ruff format .         # 2. THEN format — fixes can leave code needing reformat
uv run ruff check .          # 3. see what's left; --fix exiting clean != zero violations
```

Order matters: `--fix` rewrites imports/comprehensions that then need reformatting.
For what remains:

- Fix the code. Reach for suppressions only when the violation is intentional, and
  then the narrowest one: specific `# noqa: <CODE>` > per-file-ignores > global
  `ignore`. Never make a red gate green by deleting rules from `select`.
- Some fixes are deliberately held back as unsafe (could change behavior). Review
  them explicitly with `uv run ruff check . --fix --unsafe-fixes --diff` before
  applying.
- In GitHub Actions logs, `uv run ruff check . --output-format=github` emits
  file/line annotations on the PR (the workflow YAML itself is python-ci
  territory).

### 7. Verify done

```bash
uv run ruff check . && uv run ruff format --check . && echo LINT-OK
python3 "${CLAUDE_SKILL_DIR}/scripts/check_ruff_config.py" --root .
```

## Output spec

Done means all of:

- `pyproject.toml` has `[tool.ruff]` with an explicit `select`, `E501` ignored
  while the formatter is in use, and a resolved `target-version` (or
  `requires-python`).
- Ruff pinned in dev dependencies (and optionally `required-version` in config).
- `uv run ruff check .` and `uv run ruff format --check .` both exit 0.
- No leftover `.flake8` / `.isort.cfg` / `[tool.black]` / `[tool.isort]`, and no
  black/flake8/isort in dev dependencies (unless the documented hybrid pattern).
- Migrations: the mechanical reformat isolated in its own commit; suppressions
  carry rule codes and reasons.
- `scripts/check_ruff_config.py` reports 0 errors.

## Failure modes & gotchas

| Symptom | Cause | Fix |
| --- | --- | --- |
| Ruff installed but finds too little (pre-0.16) or floods CI after an upgrade (0.16+) | Running on the default rule set, which changed from `E`+`F` to 413 rules in 0.16 | Write an explicit `select` (step 3) — it replaces the defaults, so upgrades stop moving the gate |
| E501 violations the formatter refuses to fix | Linter and formatter both own line length | `ignore = ["E501"]`; the formatter wraps what it can |
| Routine Ruff upgrade suddenly fails checks | `select = ["ALL"]` auto-enables new rules | Explicit `select`; pin the Ruff version |
| Formatter and linter fight (commas, quotes, indentation) | `COM812`/`COM819`, `Q000`–`Q004`, `D203`/`D206`/`D300`, `W191`, `E111`/`E114`/`E117` (and `ISC002` without `ISC001` + `allow-multiline = false`) conflict with `ruff format` | Drop them from `select`/add to `ignore` — see [conflicting rules](https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules) |
| `--fix` deletes `# noqa: XY123` comments | `RUF100` treats unknown codes as unused suppressions | `external = ["XY"]` in `[tool.ruff.lint]` |
| Autofix emits syntax that breaks the oldest supported Python | No `target-version` / `requires-python` → py310 assumed | Set `target-version` to the real minimum |
| Excluded files still linted when paths are passed one-by-one | Explicit file args bypass `exclude` ([ruff#9585](https://github.com/astral-sh/ruff/issues/9585)) | Use per-file-ignores for must-hold rules; hook-layer wiring belongs to python-precommit |
| `ruff check --fix` exits clean, CI still red | Only *safe* fixes auto-apply; the rest still report | Re-run plain `check`; fix manually or review `--unsafe-fixes --diff` |
| Files keep flip-flopping between formats | Black (or an IDE Black plugin) still active alongside Ruff | One formatter only — remove Black, update editor settings |
| Old `.flake8` / `[tool.black]` settings "stopped working" | Ruff never reads them | Translate into `[tool.ruff]`, then delete the originals |
| Passes locally, fails elsewhere | Version drift across dev/CI/hooks | Same pinned version everywhere; `required-version` makes mismatch a hard error |
| Expected Ruff to format YAML/Markdown/TOML | Python-only by design; since 0.16 Python *code fences* in Markdown are formatted by default (opt out with `fmt: off` comments or `extend-exclude`) | python-precommit skill covers non-Python formatting; scope Prettier/mdformat so they do not fight Ruff on fenced Python |
| First CI run after adding Ruff fails hard | No local cleanup pass before wiring the gate | Run step 6 locally, commit, then gate |
| `ruff check` green but diffs look unformatted | Lint and format are separate concerns — `check` doesn't verify formatting | Always run both gates (step 7) |

## Bundled resources

- `references/rule-selection.md` — rule-prefix→origin map, tiered adoption
  strategy, `select` vs `extend-select` vs `ALL` trade-offs, per-file-ignore
  conventions, isort/pydocstyle/bugbear sub-tables, fix-safety knobs.
- `references/migration.md` — old-command→Ruff mapping, Black/isort/Flake8 config
  key translation, Flake8-plugin→prefix table, custom-plugin hybrid, incremental
  adoption for large legacy codebases.
- `scripts/check_ruff_config.py` — read-only config sanity checker; exits non-zero
  on findings. Run `python3 "${CLAUDE_SKILL_DIR}/scripts/check_ruff_config.py" --root <repo>`
  (`--strict` to fail on warnings too).
