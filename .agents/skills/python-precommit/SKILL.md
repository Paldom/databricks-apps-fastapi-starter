---
name: python-precommit
description: Configures pre-commit for a Python repo — a .pre-commit-config.yaml with ruff, mypy, hygiene, commit-message and pre-push hooks, plus non-Python file formatting and validation (YAML, JSON, TOML, Markdown), kept in sync with CI. Use for 'set up pre-commit', 'add git hooks', 'devs keep skipping hooks with --no-verify', 'format the YAML and Markdown', 'enforce conventional commits'. Not for Claude Code agent hooks or CI workflows.
license: MIT
---

# python-precommit

Set up and maintain the [pre-commit](https://pre-commit.com) framework in the
user's Python repository. The value is not "write a YAML file" — a competent
model can do that. The value is avoiding the specific traps that make hook
setups silently useless: unpinned or drifted hook versions that disagree with
CI, ruff hooks that auto-fix and let the commit through anyway, mypy hooks
running in an empty environment, the archived Prettier mirror, and slow hooks
that train everyone to type `--no-verify`.

## When NOT to use

- **Claude Code / agent hooks** (PostToolUse, settings.json, AGENTS.md rules,
  which enforcement layer should run what) — the agent-guardrails skill, if
  installed, owns that.
- **CI workflow authoring** beyond the single pre-commit mirror job below
  (matrices, required checks, caching, action SHA pinning at scale) — the
  python-ci skill.
- **Choosing ruff rules or fixing lint/format errors** — the python-lint skill.
- **Choosing or configuring the type checker itself** — the python-typing skill.
- **Release automation that consumes conventional commits** (version bumps,
  changelogs, publishing) — the python-release skill. This skill only enforces
  the message format at commit time.
- **Repo-level secret scanning / push protection / Dependabot for package
  dependencies** — the python-supply-chain skill.

## Operating principles

1. **The hook is convenience; CI is enforcement.** `git commit --no-verify`
   bypasses everything, silently, with no audit trail. Never present a hook as
   a guarantee. Every check in `.pre-commit-config.yaml` must also run in CI
   ([switowski.com/blog/pre-commit-vs-ci](https://switowski.com/blog/pre-commit-vs-ci/)).
2. **Commit stage stays fast** — a few seconds. Slow hooks are the main driver
   of `--no-verify` habits. Slow checks go to `pre-push` or CI.
3. **Pin everything.** Every `repo:` gets a pinned `rev:`; an unpinned or
   branch-pinned hook is both irreproducible and a supply-chain hole (installing
   hooks clones and executes arbitrary repos —
   [pre-commit#942](https://github.com/pre-commit/pre-commit/issues/942)).
4. **Never enable a hook that fails on the existing tree.** Run it over all
   files, fix the fallout, commit, then it starts gating.

## Workflow

### 1. Survey the repo

Before writing config, check:

```bash
ls .pre-commit-config.yaml .git/hooks/pre-commit 2>/dev/null  # existing setup?
grep -n 'ruff\|mypy' pyproject.toml          # versions to keep hooks in lockstep with
ls .github/workflows/ 2>/dev/null            # workflows -> add check-jsonschema; CI mirror target
ls package.json 2>/dev/null                  # Node already present? -> Prettier is cheap here
```

Record the ruff (and mypy) versions in the dev dependency group — hook revs
must match them, or local and CI results will disagree (the "double
accounting" problem, step 7).

### 2. Write the Python baseline

`.pre-commit-config.yaml` at the repo root. Pin every `rev` (tags shown; see
step 7 for SHA freezing), then run `pre-commit autoupdate` once to resolve
current releases and review the diff — the revs below are known-good examples,
not the latest.

```yaml
# .pre-commit-config.yaml
default_install_hook_types: [pre-commit, commit-msg, pre-push]

repos:
  # Hygiene — cheap, universal
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

  # Python lint + format. Order matters: fixer first, formatter second.
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.6    # keep in lockstep with the ruff version in your dev deps
    hooks:
      - id: ruff-check          # named `ruff` on older revs
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
```

Two load-bearing details:

- pre-commit itself fails any hook that modified files ("files were modified by
  this hook"), so an auto-fix never slips into a commit unstaged; the fail →
  `git add` → recommit loop is expected behavior — tell the user so once.
  `--exit-non-zero-on-fix` adds nothing under pre-commit; it matters when the
  same `ruff check --fix` runs *outside* it (a Makefile or CI step), where a
  fixed file otherwise exits 0 and reads as clean.
- Excludes under pre-commit are special: pre-commit passes filenames
  explicitly, which can bypass exclusions from a `pyproject.toml` in an
  excluded subdirectory ([ruff#9585](https://github.com/astral-sh/ruff/issues/9585)).
  Put excludes in the **top-level** ruff config, and for certainty add a
  hook-level `exclude: ^(vendored|migrations)/` regex in the pre-commit config.

### 3. Non-Python files — format AND validate

Formatting is not validation: a malformed GitHub workflow or `pyproject.toml`
formats fine. Add both layers, and pick the formatter route by toolchain, not
habit:

- **`package.json` present** (Node already first-class) → Prettier via the
  maintained fork — the original `pre-commit/mirrors-prettier` is **archived**,
  broken since Prettier v3; older tutorials still point at it.
- **Pure-Python repo** → prefer the Node-free stack (mdformat for Markdown,
  taplo for TOML, yamllint for YAML — more tools, zero npm; recipes and
  trade-offs in [references/config-recipes.md](references/config-recipes.md)).
  Prettier's hook env bootstraps its own Node, and that bootstrap (first-run
  download, proxies, unusual arches) is the top source of "the prettier hook
  keeps erroring" reports. A team that wants one formatter across
  YAML/Markdown/JSON can still choose Prettier — state the trade-off and see
  the bootstrap fixes in the gotchas.

Prettier route:

```yaml
  - repo: https://github.com/rbubley/mirrors-prettier   # maintained fork
    rev: v3.9.6
    hooks:
      - id: prettier
        types_or: [yaml, markdown, json]   # never .py/.pyi — no fight with ruff
        args: [--prose-wrap=always]
        # Ruff >= 0.16 formats Python code fences inside Markdown by default; Prettier
        # leaves fence contents alone, so the two coexist — but do not add a second
        # Python formatter for Markdown.

  - repo: https://github.com/abravalheri/validate-pyproject
    rev: v0.26
    hooks:
      - id: validate-pyproject
        additional_dependencies: ["validate-pyproject-schema-store[all]"]

  - repo: https://github.com/python-jsonschema/check-jsonschema
    rev: 0.38.0
    hooks:
      - id: check-github-workflows
      - id: check-dependabot
```

The validators (validate-pyproject, check-jsonschema) apply to both routes;
the yamllint-vs-Prettier conflict is covered in
[references/config-recipes.md](references/config-recipes.md).

### 4. Commit-message stage — conventional commits

Only if the user wants commit-format enforcement (it feeds changelog/release
automation, which the python-release skill owns):

```yaml
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v4.4.0
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
```

`commit-msg` hooks only run if that hook *type* is installed —
`default_install_hook_types` (already in the baseline) handles this. Without
it, plain `pre-commit install` installs only the pre-commit stage and the
check silently never runs.

### 5. Pre-push stage — slow checks

mypy and tests are too slow for every commit. Run them once per push via
`repo: local` hooks that use the project's own environment (this also sidesteps
the mirrors-mypy isolated-env pitfall — see gotchas):

```yaml
  - repo: local
    hooks:
      - id: mypy
        name: mypy (pre-push)
        entry: uv run mypy .
        language: unsupported
        pass_filenames: false
        stages: [pre-push]
      - id: pytest
        name: pytest (pre-push)
        entry: uv run pytest -q
        language: unsupported
        pass_filenames: false
        stages: [pre-push]
```

`language: unsupported` (the pre-commit >= 4.4 name; `system` on older versions)
means the tool must exist in each clone — fine here because `uv run` resolves the
project's locked versions (pip fallback: `entry: python -m mypy .`).
Budget: pre-push under ~30 s; anything slower is CI-only.

### 6. Install and first run

```bash
uv add --dev pre-commit          # pins pre-commit itself in uv.lock
uv run pre-commit install        # installs every stage in default_install_hook_types
uv run pre-commit run --all-files
```

(Without uv: `python -m pip install pre-commit`, then the same `pre-commit …`
commands — noted once, applies to all commands in this skill.)

The first `run --all-files` will be slow (hook environments are built on
demand) and will likely fail while fixing files — re-run until clean, review,
and commit the formatting changes **separately** from the config. Hooks are
per-clone and not tracked by git, so add the install step to the contributor
docs or a `make setup` target; CI is the only backstop for clones that never
ran it.

### 7. Mirror in CI and keep versions in sync

Local hooks and CI must run the **same config at the same versions**. The
mirror job (this one job is in scope here; everything else CI belongs to the
python-ci skill):

```yaml
# .github/workflows/pre-commit.yml
name: pre-commit
on:
  pull_request:
  push: { branches: [main] }
jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7        # pin actions to full SHAs in real use
      - uses: actions/setup-python@v7    # (re-tagged releases are a real attack)
        with: { python-version: "3.12" }
      - run: python -m pip install pre-commit==4.6.2   # match your uv.lock version
      - run: pre-commit run --all-files --show-diff-on-failure
```

Because CI runs the identical `.pre-commit-config.yaml`, hook revs cannot
drift between local and CI. What still drifts: the hook `rev` vs the same
tool's version in your dev dependency group (ruff in both places is the
classic). Keep them in lockstep; automate rev updates with one of — Dependabot's
pre-commit ecosystem, pre-commit.ci's scheduled autoupdate, or a monthly
`pre-commit autoupdate` PR (reviewed, never blind). For security-sensitive
repos, `pre-commit autoupdate --freeze` pins revs to full commit SHAs, immune
to re-tagging. Details, the pre-commit.ci autofix debate, and the
maintenance-only status of `pre-commit/action` are in
[references/sync-and-ci.md](references/sync-and-ci.md).

### 8. Verify

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/check_precommit_config.py" .pre-commit-config.yaml  # footgun lint, read-only
uv run pre-commit run --all-files        # exits 0 on a clean tree
git commit --allow-empty -m "bad msg"    # commit-msg hook must reject (if step 4 used)
```

The script (in this skill's folder) checks for unpinned revs, the archived
Prettier mirror, missing `--exit-non-zero-on-fix`, mirrors-mypy without
`additional_dependencies`, unscoped Prettier, wrong hook order, and stages
that were configured but never installed. It never modifies anything.

## Output spec — what done looks like

- `.pre-commit-config.yaml` at the repo root; **every** remote repo has a
  pinned `rev` (tag at minimum, SHA via `--freeze` where warranted).
- `default_install_hook_types` covers every stage any hook uses.
- `pre-commit run --all-files` exits 0 on the current tree.
- A typical commit completes its hooks in a few seconds.
- CI runs the identical config (`pre-commit run --all-files` job or
  pre-commit.ci) — no separately-versioned ruff/mypy invocations duplicating
  the hooks.
- A rev-update mechanism exists (Dependabot / pre-commit.ci / scheduled
  autoupdate PR).
- Contributor docs or Makefile mention `pre-commit install`.
- `scripts/check_precommit_config.py` reports 0 errors.

## Failure modes & gotchas

- **Ruff "fixed" the files but the commit went through with the old content**
  → `--exit-non-zero-on-fix` missing from the ruff hook args (step 2).
- **Commit fails, developer confused, files "already fixed"** → auto-fix hooks
  leave fixes unstaged by design; `git add -u` and recommit. Say this once in
  contributor docs.
- **Passes locally, fails in CI (or vice versa)** → version skew: hook `rev`
  vs dev-dependency vs whatever CI installs. Fix by running the same config in
  CI and syncing revs (step 7). This "double accounting" is the top recurring
  pre-commit complaint.
- **Ruff lints files that are in its exclude list** → pre-commit passes paths
  explicitly; nested-config excludes may be bypassed
  ([ruff#9585](https://github.com/astral-sh/ruff/issues/9585)). Top-level
  excludes + hook-level `exclude:` regex.
- **mypy hook reports import errors / misses real errors** →
  `pre-commit/mirrors-mypy` runs in an isolated env without your project's
  dependencies, and only sees staged files (no whole-program view). Either add
  `additional_dependencies: [types-…, pydantic, …]` and accept partial
  checking, or prefer the local `uv run mypy .` pre-push hook (step 5).
- **Prettier hook broken or frozen** → `pre-commit/mirrors-prettier` is
  archived; use `rbubley/mirrors-prettier`. Still erroring at hook-env install
  (node download failures — proxies, offline machines, unusual arches)? Add
  `language_version: system` to the prettier hook to reuse the machine's own
  Node (which must then exist everywhere, including CI), or switch a
  pure-Python repo to the Node-free stack (step 3).
- **Agent-authored changes keep failing these hooks at the owner's commit**
  (prettier reformats, whitespace fixers fire) → a parity gap in the agent
  layer, not a pre-commit problem: the agent's Stop gate must run this same
  config (`pre-commit run --files <changed>`) before signing off — the
  agent-guardrails skill ships that gate. Never let an agent re-implement a
  subset of the commit gate; subsets drift.
- **Prettier and ruff fight over files** → always scope Prettier with
  `types_or: [yaml, markdown, json]`. Note the type identifier for TypeScript
  is `ts`, not `typescript` — the wrong name silently matches nothing.
- **yamllint fails files Prettier just formatted** → their defaults genuinely
  conflict (comment spacing, indentation); reconcile configs explicitly
  (see references/config-recipes.md) or drop one of them.
- **Hooks that fight each other, reformatting in a loop** → order is fixer →
  formatter (`ruff-check --fix` then `ruff-format`); formatters last.
- **commit-msg / pre-push hooks configured but never firing** → that hook type
  was never installed. `default_install_hook_types` or
  `pre-commit install --hook-type commit-msg --hook-type pre-push`.
- **New contributor has no hooks at all** → per-clone install, by design.
  Document it; rely on the CI mirror as backstop.
- **Everyone bypasses with `--no-verify`** → the hooks are too slow or too
  noisy; that is a design failure, not a discipline failure. Profile with
  `pre-commit run --verbose`, move slow hooks to pre-push/CI, and offer
  `SKIP=<hook-id> git commit …` as the surgical alternative. Do not promise
  any local mechanism can prevent bypass.
- **First run downloads the world** → expected; environments are cached in
  `~/.cache/pre-commit` afterward. Warn users once.
- **Coverage thresholds or full test suites in the pre-commit stage** →
  community consensus is these belong in CI (or at most pre-push); commit-time
  coverage gates get bypassed and resented.

## Unsettled debates — present options, don't assert winners

- **Autofix in CI** — dominant stance: CI enforces, never mutates
  (`pre-commit run --all-files`, fail on diff). pre-commit.ci's autofix
  (auto-commits formatting to PRs) is a deliberate exception some teams adopt;
  note it has documented gaps auto-fixing `.github/workflows` files.
- **prek** ([github.com/j178/prek](https://github.com/j178/prek)) — Rust,
  uv-powered, drop-in reader of the same `.pre-commit-config.yaml`, faster
  installs/updates (community-reported) and native monorepo support; newer and
  less battle-tested (0.5.x as of 2026-09). Renamed commands: `install-hooks` →
  `prepare-hooks`, `autoupdate` → `update`, `SKIP` → `PREK_SKIP`; prek-only config
  extensions can trip auditors that expect pure pre-commit YAML. Reasonable to offer when speed or monorepos hurt;
  `uv add --dev prek && uv run prek install`.
- **"Pre-commit is dead under agents"** — a minority position (Massdriver
  talk, mid-2026) argues high-frequency agent edits make local hooks
  impractical and checks should consolidate in CI. Most current stacks keep
  pre-commit as the fast local layer; if the user's repo is agent-heavy, note
  the trade-off and let them choose. Which layer (agent hook vs git hook vs
  CI) runs which check is the agent-guardrails skill's territory.

## Bundled material

- [references/config-recipes.md](references/config-recipes.md) — complete
  annotated configs: full baseline, Prettier vs Node-free stacks, validators,
  conventional-commit and pre-push recipes, uv lockfile hooks, optional secret
  scan, ruff-in-Markdown, monorepo/local-hook patterns.
- [references/sync-and-ci.md](references/sync-and-ci.md) — the double
  accounting problem, CI mirror recipes, pre-commit.ci, rev-update automation,
  SHA freezing and hook supply chain, bypass honesty, prek, stage-placement
  budgets.
- [scripts/check_precommit_config.py](scripts/check_precommit_config.py) —
  read-only footgun linter for an existing `.pre-commit-config.yaml`
  (`python3 "${CLAUDE_SKILL_DIR}/scripts/check_precommit_config.py" [path] [--strict]`; non-zero
  exit on findings).
