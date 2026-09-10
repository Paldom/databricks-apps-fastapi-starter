# pre-commit config recipes

Complete, annotated `.pre-commit-config.yaml` building blocks for a Python
repo. Every `rev` shown is a known-good example from real configs — after
copying, run `pre-commit autoupdate` once and review the diff to land on
current releases. Never leave a `rev` unpinned or pointed at a branch.

**Contents:**

1. [Full baseline config](#1-full-baseline-config)
2. [Non-Python formatting — Prettier route](#2-non-python-formatting--prettier-route)
3. [Non-Python formatting — Node-free route](#3-non-python-formatting--node-free-route)
4. [Validators (formatting is not validation)](#4-validators-formatting-is-not-validation)
5. [Conventional commits (commit-msg stage)](#5-conventional-commits-commit-msg-stage)
6. [Pre-push stage — mypy and tests](#6-pre-push-stage--mypy-and-tests)
7. [uv lockfile hooks](#7-uv-lockfile-hooks)
8. [Optional: secret scanning hook](#8-optional-secret-scanning-hook)
9. [Ruff extras — Markdown code blocks, excludes, ordering](#9-ruff-extras--markdown-code-blocks-excludes-ordering)
10. [Monorepos and local hooks](#10-monorepos-and-local-hooks)

## 1. Full baseline config

Everything from the SKILL.md workflow assembled, with the optional stages
included:

```yaml
# .pre-commit-config.yaml
# Install: uv run pre-commit install   (installs all stages listed below)
default_install_hook_types: [pre-commit, commit-msg, pre-push]

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
        args: [--allow-multiple-documents]
      - id: check-toml
      - id: check-json
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: detect-private-key
      # Optional — blocks local commits directly to main. Solo maintainers
      # who commit to main on purpose should skip this one.
      # - id: no-commit-to-branch
      #   args: [--branch, main]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.10          # lockstep with ruff in [dependency-groups] dev
    hooks:
      - id: ruff-check     # `ruff` on revs before the id rename
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/rbubley/mirrors-prettier
    rev: v3.8.2
    hooks:
      - id: prettier
        types_or: [yaml, markdown, json]
        args: [--prose-wrap=always]

  - repo: https://github.com/abravalheri/validate-pyproject
    rev: v0.25
    hooks:
      - id: validate-pyproject
        additional_dependencies: ["validate-pyproject-schema-store[all]"]

  - repo: https://github.com/python-jsonschema/check-jsonschema
    rev: 0.37.1
    hooks:
      - id: check-github-workflows
      - id: check-dependabot

  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v4.0.0
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]

  - repo: local
    hooks:
      - id: mypy
        name: mypy (pre-push)
        entry: uv run mypy .
        language: unsupported   # `system` on pre-commit < 4.4
        pass_filenames: false
        stages: [pre-push]
      - id: pytest
        name: pytest (pre-push)
        entry: uv run pytest -q
        language: unsupported   # `system` on pre-commit < 4.4
        pass_filenames: false
        stages: [pre-push]
```

Stage placement budgets (practitioner heuristic, not a standard):

| Stage | Budget | Belongs here |
| --- | --- | --- |
| pre-commit | < ~5 s | formatters, staged-file lint, hygiene, secret patterns |
| pre-push | < ~30 s | mypy full run, quick test suite, builds |
| CI only | minutes | full pytest + coverage, audits, anything needing network/credentials |

## 2. Non-Python formatting — Prettier route

Prettier is the mature choice for YAML/JSON/Markdown when Node is already in
the toolchain (`package.json` present). Three catches:

- **The original mirror is archived.** `pre-commit/mirrors-prettier` broke
  with Prettier v3's plugin changes and gets no updates; many tutorials still
  reference it. Use the maintained fork `rbubley/mirrors-prettier` (as above).
- **The hook env bootstraps its own Node** (via nodeenv). That first-run
  download is the top flake source — proxies, offline machines, unusual
  architectures. Where it bites, pin the hook to the machine's Node instead:

  ```yaml
      - id: prettier
        language_version: system   # reuse installed Node; skips the nodeenv download
  ```

  This trades the download flake for a new requirement: Node must exist on
  every committing machine *and* in the CI mirror job. If that requirement is
  unwanted, use the Node-free route (§3).
- **Prettier cannot read `pyproject.toml`.** If you need to configure it
  (print width, prose wrap), it takes its own `.prettierrc`/`.prettierrc.toml`
  — the one place the single-config-file goal breaks. Add a `.prettierignore`
  for generated files and lockfiles.

Scoping rules:

- `types_or: [yaml, markdown, json]` keeps it off `.py`/`.pyi` files — no
  overlap with ruff, ever.
- File-type identifiers come from pre-commit's `identify` library. TypeScript
  is `ts` (not `typescript`); the wrong name silently matches nothing.
- Cost: Prettier drags a Node runtime into the hook environment ("Node tax").
  Real objection is dependency footprint, not output quality. If the repo
  already has `package.json`, this is a non-issue.

## 3. Non-Python formatting — Node-free route

For a strict no-Node repo, replace Prettier with per-format tools. You trade
one dependency for three or four smaller ones, each with its own config and
update cadence — not free, state the trade-off.

```yaml
  - repo: https://github.com/hukkin/mdformat
    rev: 1.0.0
    hooks:
      - id: mdformat
        additional_dependencies: [mdformat-gfm, mdformat-ruff]  # tables + Python code blocks via ruff

  - repo: https://github.com/ComPWA/taplo-pre-commit
    rev: v0.9.3
    hooks:
      - id: taplo-format      # formats TOML; taplo also validates against schemas
      - id: taplo-lint

  - repo: https://github.com/adrienverge/yamllint
    rev: v1.38.0
    hooks:
      - id: yamllint
        args: [--strict]
```

Notes and caveats:

- **Markdown**: `mdformat` (Python, plugin-based) is the established choice;
  `mdformat-ruff` delegates embedded Python code blocks to ruff. `rumdl`
  (Rust, pip-installable, markdownlint-compatible rules) is a promising
  newcomer — real and functional, but treat "everyone is switching" claims
  cautiously.
- **TOML**: `taplo` is the most mature TOML toolkit. `pyproject-fmt` and
  `toml-sort` are narrower (pyproject.toml-specific); beware that some
  AST-round-trip TOML formatters strip human-written comments — check on a
  scratch copy first.
- **YAML is the genuinely contentious format**: yamllint is a *linter*, not a
  formatter; Google's `yamlfmt` and `ruamel.yaml` disagree with each other
  (and with Prettier) on list indentation and multiline strings. Many teams
  run yamllint only, or reluctantly keep Prettier for YAML because its output
  is predictable.
- **yamllint + Prettier together**: yamllint's defaults (e.g. two spaces
  before inline comments) reject Prettier's output. If running both, reconcile
  explicitly, e.g. `.yamllint.yaml`:

```yaml
extends: default
rules:
  line-length: {max: 120}
  comments: {min-spaces-from-content: 1}   # accept Prettier's style
  truthy:
    ignore: |
      .github/workflows/*.yml              # `on:` keyword false positive
```

- **JSON** is low-stakes: Prettier, or `pre-commit-hooks`' `pretty-format-json`,
  or leave it to `check-json` validation only.

## 4. Validators (formatting is not validation)

A formatter happily beautifies a structurally broken file. Pair it with schema
validation:

| Tool | Validates | Hook ids |
| --- | --- | --- |
| [validate-pyproject](https://github.com/abravalheri/validate-pyproject) | `pyproject.toml` against PEP + tool schemas | `validate-pyproject` (+ `validate-pyproject-schema-store[all]` as additional dependency to cover `[tool.*]` tables) |
| [check-jsonschema](https://github.com/python-jsonschema/check-jsonschema) | GitHub workflows, Dependabot config, ReadTheDocs, arbitrary JSON/YAML vs schema | `check-github-workflows`, `check-dependabot`, `check-readthedocs` |
| [yamllint](https://github.com/adrienverge/yamllint) | YAML syntax + style | `yamllint` |
| `pre-commit-hooks` | parse-only sanity | `check-yaml`, `check-toml`, `check-json` |

`validate-pyproject` is close to universal best practice for any packaged
project; `check-github-workflows` for any repo with `.github/workflows/`.

## 5. Conventional commits (commit-msg stage)

Commit-format enforcement is the hidden prerequisite of changelog/release
automation — one non-conforming commit silently breaks automated versioning.

```yaml
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v4.0.0
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
        args: [--strict, feat, fix, docs, chore, refactor, test, ci, build, perf]  # optional: restrict types
```

Alternatives:

- **commitizen** (`commitizen check --commit-msg-file` via its own hook repo)
  if the team already uses `cz commit` for authoring.
- **commitlint** (Node) if the repo is a JS-adjacent monorepo already running
  husky/commitlint conventions.

Gotchas:

- The hook only fires if the `commit-msg` hook type is installed
  (`default_install_hook_types` or `pre-commit install --hook-type commit-msg`).
  A configured-but-uninstalled commit-msg hook fails silently — the most
  common "it doesn't work" report.
- Enforcement has social cost for OSS contributors; consider enforcing in CI
  on PR titles instead (squash-merge repos) — that variant belongs to CI/release
  tooling, not this config.

## 6. Pre-push stage — mypy and tests

Two ways to run mypy as a hook; prefer the local hook:

| Approach | Pros | Cons |
| --- | --- | --- |
| `repo: local`, `entry: uv run mypy .`, `pass_filenames: false`, `stages: [pre-push]` | Uses the project's locked mypy + all real dependencies; whole-program view; one version to sync | Requires the project env on every machine (true anyway) |
| [`pre-commit/mirrors-mypy`](https://github.com/pre-commit/mirrors-mypy) | Isolated, no project env needed | Runs **without your dependencies** — import errors or silently missing stubs unless you enumerate `additional_dependencies`; sees only staged files, so cross-file breakage escapes; second mypy version to keep in sync |

If mirrors-mypy is chosen anyway:

```yaml
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v2.3.1
    hooks:
      - id: mypy
        files: ^(src|tests)/
        additional_dependencies: [pytest, types-requests]  # every import mypy must see
```

Do not "fix" the missing-deps problem with a blanket `--ignore-missing-imports`
— it silences real errors. Configuring mypy itself (strictness, overrides) is
the python-typing skill's territory.

Tests at pre-push: keep it to a fast subset (`pytest -q -m "not slow"`) if the
suite exceeds ~30 s; the full suite belongs to CI.

## 7. uv lockfile hooks

Official hooks from [astral-sh/uv-pre-commit](https://github.com/astral-sh/uv-pre-commit)
([docs](https://docs.astral.sh/uv/guides/integration/pre-commit/)):

```yaml
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.12.12
    hooks:
      - id: uv-lock        # keeps uv.lock in sync with pyproject.toml
      # - id: uv-export    # optional: syncs requirements.txt from uv.lock
```

Useful when contributors edit `pyproject.toml` and forget `uv lock` — the
commit fails until the lockfile matches.

## 8. Optional: secret scanning hook

```yaml
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.30.1
    hooks:
      - id: gitleaks
```

Honesty requirement: a local secrets hook is a fast-feedback courtesy, **not
protection** — `--no-verify` skips it silently. If secrets matter (they do),
the repo needs server-side push protection and a CI scan as the real layers;
that architecture is the python-supply-chain skill's territory. Never present
this hook alone as the fix for "stop keys getting committed".

## 9. Ruff extras — Markdown code blocks, excludes, ordering

**Format Python code blocks inside Markdown** — on by default since Ruff 0.16
(2026-07-23; fences tagged python/py/python3/py3/pyi/pycon), and the `ruff-format`
hook already lists `markdown` in its `types_or`, so a current rev needs nothing
extra (shown explicitly here for older revs):

```yaml
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.6
    hooks:
      - id: ruff-format
        types_or: [python, pyi, jupyter, markdown]   # markdown NOT in the default set
```

```toml
# pyproject.toml — only if you want to OPT OUT for some files
[tool.ruff]
extend-exclude = ["CHANGELOG.md"]   # or `<!-- fmt: off -->` comments around a block
```

If mdformat is in play, prefer `mdformat-ruff` instead of double-formatting.

**Excludes under pre-commit** ([ruff#9585](https://github.com/astral-sh/ruff/issues/9585),
same class as isort#1872): pre-commit passes filenames explicitly; a
`pyproject.toml` inside an excluded subdirectory is not honored. Mitigations,
strongest first:

1. Hook-level exclude in `.pre-commit-config.yaml`:
   `exclude: ^(vendored|migrations|examples/legacy)/`
2. Top-level `[tool.ruff] extend-exclude` (the ruff-pre-commit hooks pass
   `--force-exclude` so top-level excludes apply to explicitly-passed files).

**Ordering**: fixers before formatters — `ruff-check --fix` can rewrite
imports or collapse comprehensions that then need reformatting, so
`ruff-format` runs last. Astral's own repos go further with `priority:` keys
(read-only checks → fixers → second-pass formatters); for a single-language
repo, "ruff-check then ruff-format, Prettier scoped away from Python" is
enough.

## 10. Monorepos and local hooks

- `repo: local` + `language: unsupported` (alias of `system`, pre-commit >= 4.4) hooks run whatever is on PATH — zero hook
  environments, but every machine and CI runner must provide the tool (use
  `uv run …` entries so the project env provides it).
- uv-workspace monorepos: replace per-package hook stanzas with a few
  workspace-level local hooks (`workspace-ruff-check`, `workspace-mypy`, …)
  driven by a script that discovers workspace members — the pattern Apache
  Airflow's tooling uses; it collapsed a 340-line config to ~150.
- Native monorepo support (per-subproject configs) is a headline feature of
  prek (see [sync-and-ci.md](sync-and-ci.md)); the original pre-commit does
  not have it.
- Files in a hook's `files:`/`exclude:` are regexes on repo-relative paths —
  anchor them (`^docs/`) or they substring-match anywhere.
