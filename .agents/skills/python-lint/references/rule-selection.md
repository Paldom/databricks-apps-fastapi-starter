# Ruff rule selection and tuning

**Contents:** [How selection works](#how-selection-works) ·
[Rule prefix → origin map](#rule-prefix--origin-map) ·
[Tiered adoption strategy](#tiered-adoption-strategy) ·
[Per-file-ignores conventions](#per-file-ignores-conventions) ·
[Sub-table options](#sub-table-options) · [Fix safety](#fix-safety) ·
[Formatter-conflicting rules](#formatter-conflicting-rules) · [Sources](#sources)

## How selection works

- Ruff's default set changed in 0.16 (2026-07-23): from **only `E` and `F`** (59
  rules) to **413 rules** spanning `B`, `UP`, `SIM`, `PL` and more, with 18 former
  `E`/`F` defaults (E401, E402, E501-adjacent E7xx style codes, F403, F405, …)
  removed — see https://docs.astral.sh/ruff/default-rules/. (Even before 0.16
  the default was `E4`/`E7`/`E9` + `F`, never all of `E`.) The lesson is
  unchanged: write `[tool.ruff.lint] select` explicitly so the enabled set is
  yours, not the release's.
- `select` **replaces** the default set; `extend-select` **adds to** whatever the
  current basis is. Trade-off, both positions defensible:
  - `select` (Astral's documented lean, [docs.astral.sh/ruff/linter/](https://docs.astral.sh/ruff/linter/)) —
    the enabled set is fully explicit in one place; upgrades cannot silently
    change it.
  - `extend-select` (recommended by some guides, e.g. pydevtools) — builds on
    defaults, shorter config; but the effective set now depends on what the
    installed Ruff version considers default.
  Prefer `select` for packages with multiple contributors; the explicitness is
  worth three extra lines.
- `select = ["ALL"]` enables every rule **including ones added in future Ruff
  releases** — checks break on routine upgrades with rules nobody chose. Ruff
  auto-disables a few mutually-conflicting rules under `ALL` (e.g. D203/D211),
  but that does not make it stable. If a team insists on `ALL`, pair it with a
  hard-pinned Ruff version and an explicit `ignore` list, and treat every
  version bump as a config-review event.
- Precedence: CLI flags (`--select`) override `pyproject.toml`; the nearest
  `pyproject.toml`/`ruff.toml` up the directory tree from each file wins. One
  root config covers a whole monorepo — per-package differences go in
  `per-file-ignores` keyed by path, not per-package config files.

## Rule prefix → origin map

| Prefix | Origin tool / plugin | What it catches |
| --- | --- | --- |
| `E`, `W` | pycodestyle | PEP 8 style errors / warnings |
| `F` | Pyflakes | unused imports/variables, undefined names |
| `I` | isort | import order and grouping |
| `N` | pep8-naming | naming conventions |
| `UP` | pyupgrade | outdated syntax for your target-version |
| `B` | flake8-bugbear | likely bugs and design problems |
| `C4` | flake8-comprehensions | inefficient comprehensions |
| `SIM` | flake8-simplify | needlessly complex constructs |
| `S` | flake8-bandit | security issues (asserts, subprocess, hashes) |
| `T20` | flake8-print | stray `print` / `pprint` |
| `PT` | flake8-pytest-style | pytest idioms |
| `Q` | flake8-quotes | quote style (conflicts with the formatter — skip) |
| `TID` | flake8-tidy-imports | banned/relative imports |
| `TC` (formerly `TCH`) | flake8-type-checking | imports movable into `TYPE_CHECKING` |
| `D` | pydocstyle | docstring conventions (**partial parity** — some checks missing) |
| `PL` (`PLC/PLE/PLR/PLW`) | Pylint (subset) | refactoring, magic values (`PLR2004`) |
| `C90` | mccabe | cyclomatic complexity |
| `ISC` | flake8-implicit-str-concat | implicit concatenation (formatter-safe; `ISC002` conflicts only without `ISC001`) |
| `ICN` | flake8-import-conventions | `import numpy as np`-style aliases |
| `ANN` | flake8-annotations | annotation *presence/style* — NOT type checking |
| `LOG`, `G` | flake8-logging(-format) | logging misuse |
| `FLY` | flynt | `%`/`.format` → f-string |
| `PTH` | flake8-use-pathlib | `os.path` → `pathlib` |
| `PERF` | Perflint | performance anti-patterns |
| `ARG` | flake8-unused-arguments | unused function arguments |
| `RUF` | Ruff-specific | rules with no upstream equivalent, incl. `RUF100` (unused noqa) |

Full catalog (900+ rules): [docs.astral.sh/ruff/rules/](https://docs.astral.sh/ruff/rules/).

## Tiered adoption strategy

Grow the set one tier at a time; run `ruff check .`, fix or scope, then advance.

| Tier | Add | Rationale |
| --- | --- | --- |
| 1 — baseline | `E`, `W`, `F`, `I` | old Flake8+isort parity; near-zero false positives |
| 2 — correctness | `B`, `C4`, `UP`, `SIM`, `RUF` | real-bug detectors and modernization; autofix-heavy |
| 3 — opinionated | `N`, `S`, `T20`, `PT`, `PTH`, `PERF`, `TC` | pick per project; each adds review burden |
| 4 — docs | `D` with `convention = "google"` (or numpy/pep257) | only when docstrings are a maintained artifact |

Rules of thumb:

- Enable `S` (security) only with the `tests/` per-file-ignore in place, or the
  suite drowns in `S101` (assert).
- Skip `Q`, `COM` (and `D203`/`D206`/`D300`, `W191`/`E11x`) when using `ruff format` (see
  [formatter-conflicting rules](#formatter-conflicting-rules)).
- `ANN` is high-noise; if the package uses a real type checker, that layer
  already enforces annotations where they matter.

## Per-file-ignores conventions

```toml
[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = [
    "S101",     # assert is the point of tests
    "PLR2004",  # magic values are fine in assertions
    "ARG001",   # fixtures produce "unused" arguments
]
"__init__.py" = ["F401"]      # re-export pattern
"scripts/*" = ["T201"]        # CLI scripts may print
"docs/conf.py" = ["A001"]     # sphinx shadows builtins
```

- Generated code (Django `migrations/`, protobuf output) goes in
  `extend-exclude`, not per-file-ignores — don't lint it at all.
- Keep per-file-ignores keyed by **pattern relative to the config file**; verify
  patterns actually match files (a typo silently ignores nothing). The bundled
  `check_ruff_config.py` flags non-matching patterns.
- Caution: when a runner passes file paths explicitly (pre-commit does),
  `exclude` can be bypassed ([ruff#9585](https://github.com/astral-sh/ruff/issues/9585));
  per-file-ignores are more robust than exclude for rules that must never fire.

## Sub-table options

```toml
[tool.ruff.lint.isort]
known-first-party = ["mypackage"]           # fixes first/third-party misgrouping
combine-as-imports = true
required-imports = ["from __future__ import annotations"]

[tool.ruff.lint.pydocstyle]
convention = "google"                       # or "numpy", "pep257"

[tool.ruff.lint.flake8-bugbear]
# stop B008 false positives on FastAPI-style call-in-default patterns
extend-immutable-calls = ["fastapi.Depends", "fastapi.Query"]

[tool.ruff.lint.mccabe]
max-complexity = 12
```

isort options translate from snake_case to kebab-case
(`known_first_party` → `known-first-party`); Ruff also respects
`# isort: skip` / `# isort: on/off` action comments. Parity has edge cases
around aliased imports and exotic multi-line grouping — diff one real commit
before trusting drop-in behavior.

## Fix safety

- `ruff check --fix` applies **safe fixes only** by default. A clean `--fix` run
  does not mean zero violations — unsafe-fixable and unfixable diagnostics
  still report.
- `--unsafe-fixes` (or `unsafe-fixes = true` in config) opts into
  behavior-affecting rewrites. Review with `--diff` first; unsafe fixes have
  occasionally introduced real bugs.
- Scope what autofix may touch with `fixable` / `unfixable` /
  `extend-fixable` in `[tool.ruff.lint]` — e.g. `unfixable = ["F401"]` stops
  `--fix` from deleting an import you were about to use, while still reporting it.
- Roughly speaking `--fix` clears the large majority of style debt automatically;
  the remainder needs human edits.

## Formatter-conflicting rules

When `ruff format` is in use, these lint rules fight it — leave them out of
`select` (Ruff warns about some of them at runtime):

- `E501` (line length — the formatter owns it; `ignore = ["E501"]`)
- `COM812` / `COM819` (trailing commas)
- `ISC002` — only when `ISC001` is *not* selected and `allow-multiline = false`
  (`ISC001` itself is fine with the formatter)
- `Q000`–`Q004` (quote style — set `[tool.ruff.format] quote-style` instead)
- `W191`, `E111`, `E114`, `E117`, `D203`, `D206`, `D300` (indentation/docstring
  mechanics the formatter normalizes)

Current list: https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules.

Authoritative list: [docs.astral.sh/ruff/formatter/#conflicting-lint-rules](https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules).

## Sources

- Ruff linter docs & rule catalog — <https://docs.astral.sh/ruff/linter/>, <https://docs.astral.sh/ruff/rules/>
- Ruff settings reference — <https://docs.astral.sh/ruff/settings/>
- pydevtools Ruff guide — <https://pydevtools.com/handbook/explanation/ruff-complete-guide/>
- Community config threads — <https://www.reddit.com/r/Python/comments/1dp4jrm/share_your_ruff_config/>
