# Migrating to Ruff from Black / Flake8 / isort / pyupgrade

**Contents:** [Decision guide](#decision-guide) · [Migration sequence](#migration-sequence) ·
[Command mapping](#command-mapping) · [Config key translation](#config-key-translation) ·
[Flake8 plugin → Ruff prefix](#flake8-plugin--ruff-prefix) ·
[Custom Flake8 plugins (hybrid pattern)](#custom-flake8-plugins-hybrid-pattern) ·
[Large legacy codebases](#large-legacy-codebases) · [Parity caveats](#parity-caveats) ·
[Cleanup checklist](#cleanup-checklist) · [Sources](#sources)

## Decision guide

| Scenario | Recommendation |
| --- | --- |
| New project, no legacy tooling | Ruff only (`ruff check` + `ruff format`); never install Black/Flake8/isort |
| Existing Black+Flake8 works, no pain | No urgent need — migration churn has cost; revisit when friction appears |
| Lint speed or config sprawl is real friction | Migrate; the mapping below is mechanical |
| Business-critical custom Flake8 plugin, no Ruff equivalent | Hybrid: Ruff for everything else, Flake8 scoped to that plugin |
| Huge legacy codebase, blame matters | Incremental: `--add-noqa` or changed-lines-only formatting (below) |
| Team standardizes on uv | `uv format` (experimental since uv 0.8.13) runs a bundled Ruff — keep the project's own `ruff` pin as the source of truth |

## Migration sequence

1. Install pinned Ruff: `uv add --dev "ruff==0.15.6"` (check latest, pin it).
2. Translate configs using the tables below into `[tool.ruff*]` sections.
3. Verify plugin parity (table below) for every Flake8 plugin in
   requirements/pre-commit.
4. One-time mechanical cleanup, its own commit, reviewed:
   `uv run ruff check . --fix && uv run ruff format .`
   Add that commit's SHA to `.git-blame-ignore-revs` so `git blame` skips it
   (GitHub honors this file automatically).
5. Remove old dev dependencies (black, flake8 + plugins, isort, pyupgrade,
   autoflake) and delete their config files/sections.
6. Repoint invocations: local docs/Makefile to `ruff check .` +
   `ruff format --check .`; pre-commit and CI rewiring belong to the
   python-precommit and python-ci skills respectively.

Do NOT wire any blocking gate before step 4 is committed — the first gated run
on an uncleaned tree fails hard.

## Command mapping

| Old command | Ruff equivalent |
| --- | --- |
| `flake8 .` | `ruff check .` |
| `black .` | `ruff format .` |
| `black --check --diff .` | `ruff format --check --diff .` |
| `isort .` | `ruff check --select I --fix .` |
| `isort --check .` | `ruff check --select I .` |
| `pyupgrade --py311-plus f.py` | `ruff check --select UP --fix f.py` (with `target-version = "py311"`) |
| `autoflake --remove-all-unused-imports` | `ruff check --select F401 --fix .` |

## Config key translation

Ruff reads **only** `[tool.ruff*]` (or `ruff.toml`). It silently ignores
`[tool.black]`, `[tool.isort]`, `.flake8`, and `setup.cfg` — any setting not
translated is simply lost, with no warning.

### From `[tool.black]`

| Black | Ruff |
| --- | --- |
| `line-length = 88` | `[tool.ruff] line-length = 88` |
| `target-version = ["py311"]` | `[tool.ruff] target-version = "py311"` (single string) |
| `skip-string-normalization = true` | `[tool.ruff.format] quote-style = "preserve"` |
| `skip-magic-trailing-comma = true` | `[tool.ruff.format] skip-magic-trailing-comma = true` |
| `preview = true` | no direct equivalent; Ruff has its own `preview` flag with different contents |

### From `[tool.isort]` / `.isort.cfg`

Keys move to `[tool.ruff.lint.isort]` and become kebab-case:

| isort | Ruff |
| --- | --- |
| `profile = "black"` | drop it — Ruff's `I` rules are formatter-consistent already |
| `known_first_party = ["pkg"]` | `known-first-party = ["pkg"]` |
| `combine_as_imports = true` | `combine-as-imports = true` |
| `force_sort_within_sections = true` | `force-sort-within-sections = true` |
| `add_imports = ["from __future__ import annotations"]` | `required-imports = [...]` |
| `skip` / `# isort: skip` comments | `# isort: skip` etc. respected as-is |

### From `.flake8` / `setup.cfg [flake8]`

| Flake8 | Ruff |
| --- | --- |
| `max-line-length = 100` | `[tool.ruff] line-length = 100` (then ignore `E501` if formatting) |
| `extend-ignore = E203, W503` | usually deletable — Ruff's defaults don't fight the formatter the way pycodestyle fought Black |
| `ignore = ...` | `[tool.ruff.lint] ignore = [...]` |
| `per-file-ignores = tests/*:S101` | `[tool.ruff.lint.per-file-ignores] "tests/*" = ["S101"]` |
| `exclude = ...` | `[tool.ruff] extend-exclude = [...]` |
| `max-complexity = 10` | `[tool.ruff.lint.mccabe] max-complexity = 10` + select `C90` |
| installed plugins | `select` prefixes — table below |

## Flake8 plugin → Ruff prefix

| Flake8 plugin | Ruff prefix |
| --- | --- |
| pycodestyle | `E` / `W` |
| pyflakes | `F` |
| pep8-naming | `N` |
| flake8-bugbear | `B` |
| flake8-comprehensions | `C4` |
| flake8-simplify | `SIM` |
| flake8-bandit | `S` |
| flake8-pytest-style | `PT` |
| flake8-quotes | `Q` (skip when using `ruff format`) |
| flake8-tidy-imports | `TID` |
| flake8-type-checking | `TC` |
| flake8-print | `T20` |
| flake8-docstrings / pydocstyle | `D` — **partial parity**, verify the specific checks you rely on |
| mccabe | `C90` |

Anything not in this table: search
[docs.astral.sh/ruff/rules/](https://docs.astral.sh/ruff/rules/) — Ruff
reimplements most popular plugins but not all; verify before deleting a plugin
a team relies on.

## Custom Flake8 plugins (hybrid pattern)

Ruff has no plugin API. For an in-house plugin with no Ruff equivalent:

1. Keep Flake8 installed, scoped to only that plugin's codes:
   `flake8 --select=WH .` (whatever the plugin's prefix is).
2. Declare the foreign codes so Ruff leaves their suppressions alone:

   ```toml
   [tool.ruff.lint]
   external = ["WH"]
   ```

   Without this, `RUF100` treats `# noqa: WH001` as an unused suppression and
   **deletes it on the next `--fix`**.
3. Plan an exit: file a rule request upstream or port the check to a standalone
   script; a two-linter setup is a liability, not a destination.

## Large legacy codebases

Options, in increasing order of disruption:

1. **Minimal select, grow later** — start `select = ["E", "F"]`, expand one
   prefix at a time as modules get cleaned.
2. **Bulk-suppress, then tighten** — `uv run ruff check --add-noqa .` writes a
   targeted `# noqa` on every existing violation; the gate goes green
   immediately, and the debt is visible and grep-able. Remove noqas module by
   module. (This mutates the tree — run it on a branch and review.)
3. **Changed-lines-only formatting** — [Darker](https://github.com/akaihola/darker)
   applies formatting only to lines touched by a commit, avoiding the big-bang
   reformat entirely, at the cost of a long transition with mixed styles.
4. **Big-bang reformat** — one mechanical commit, reviewed, recorded in
   `.git-blame-ignore-revs`. Simplest end state; noisiest single diff.

Whichever option: set `target-version` before any `--fix`, or `UP` rewrites can
emit syntax newer than the oldest Python the project still supports.

## Parity caveats

- **Formatter vs Black** — near-identical on large codebases per Astral's own
  benchmarks (not independently verified); known deviations around complex
  f-strings, block-open newlines, and preview styles are documented at
  [docs.astral.sh/ruff/formatter/black/](https://docs.astral.sh/ruff/formatter/black/).
  Diff a representative file before promising byte-identical output.
- **isort** — edge cases around aliased imports, inline comments, exotic
  multi-line grouping; a few projects keep isort for those files only.
- **pydocstyle (`D`)** — partial rule coverage; check the rules page for the
  specific checks in use.
- **Exact-parity expectations are the top migration friction** reported by
  users (e.g. [r/Python migration thread](https://www.reddit.com/r/Python/comments/1gvnfvi/migrating_from_black_and_flake8_to_ruff/)) —
  set the expectation of a small, reviewable style delta, not zero delta.

## Cleanup checklist

After migrating, all of these should be gone (leftovers cause silent conflicts):

- [ ] `.flake8`, `.isort.cfg`, `tox.ini [flake8]`, `setup.cfg [flake8]`/`[isort]`
- [ ] `[tool.black]`, `[tool.isort]` in `pyproject.toml`
- [ ] black / flake8 / flake8-* / isort / pyupgrade / autoflake in dev deps
- [ ] Editor settings invoking Black (VS Code `python.formatting.provider`, etc.)
- [ ] Makefile / docs / CONTRIBUTING referencing the old commands
- [ ] Old pre-commit hooks and CI steps (owned by python-precommit / python-ci)

The bundled `scripts/check_ruff_config.py` detects most of these automatically.

## Sources

- Ruff FAQ (tool replacement matrix) — <https://docs.astral.sh/ruff/faq/>
- pydevtools migration how-to — <https://pydevtools.com/handbook/how-to/how-to-replace-black-isort-flake8-pyupgrade-with-ruff/>
- Real-world OSS migration discussions — <https://github.com/qtile/qtile/discussions/4980>, <https://github.com/orgs/micropython/discussions/12914>
- Black/Flake8/Ruff comparison — <https://tenthirtyam.org/dispatches/2026/03/30/python-code-quality-black-flake8-and-ruff/>
