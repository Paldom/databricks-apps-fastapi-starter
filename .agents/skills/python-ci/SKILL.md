---
name: python-ci
description: Authors GitHub Actions quality-gate workflows for a Python repo — lint/type/test jobs, version matrices, uv caching, an all-checks-passed aggregator, required checks, rulesets, merge queues, SHA pinning, zizmor hardening. Use for 'set up continuous integration quality gates', 'make checks required', 'move branch protection to rulesets', 'harden the workflows'. Not for release pipelines or commit hooks.
license: MIT
---

# python-ci

## Purpose

Build the GitHub Actions quality gate for a Python repository: workflows that run
lint, type check, and tests across a Python version matrix with uv caching, funnel
into one `all-checks-passed` aggregator job, get enforced as required status checks
behind branch rulesets, and are hardened against the ways CI gets silently weakened
(skipped jobs that count as success, renamed matrix legs that strand PRs, mutable
action tags, over-broad `GITHUB_TOKEN` scopes, `pull_request_target` and cache
trust-boundary holes). CI is the one enforcement layer that cannot be bypassed with
`--no-verify` — treat the workflow files themselves as production code.

## When NOT to use

- **Release/publish workflows** (tag-triggered PyPI publish, trusted publishing,
  version bumps) — the python-release skill, if installed, owns those. This skill
  only ensures the quality gate a release job can `needs:` on.
- **pre-commit config or its CI mirror job** — the python-precommit skill.
- **coverage.py configuration** (`fail_under` values, `relative_files`, source
  paths) — the python-testing skill. This skill wires coverage *through the
  workflow* (per-leg artifacts, combine job placement) only.
- **Dependabot, secret scanning, CodeQL, Scorecard, SBOMs, CODEOWNERS** — the
  python-supply-chain skill.
- **Fixing the failures CI reports** (lint errors, type errors, failing tests) —
  the python-lint / python-typing skills or ordinary debugging.

## Workflow

### 1. Survey the repo before writing YAML

- Read `pyproject.toml`: which tools are configured (`[tool.ruff]`, mypy/pyright/ty,
  pytest), the `requires-python` range (it defines the matrix), and dependency
  groups (`dev` or `dependency-groups`).
- Check for a committed `uv.lock`. If present, CI must use `uv sync --locked` —
  never regenerate the lockfile in the runner; lockfile changes belong in commits.
- List existing `.github/workflows/` files; extend or replace deliberately, and
  check repo settings for merge queues (they change the trigger set — step 5).
- CI runs what the repo already defines. Do not introduce new tools or looser
  variants: the gate must run the same commands developers run locally, in
  **check mode** (`ruff check`, `ruff format --check`) — if an earlier layer
  auto-fixes, CI only verifies. A `make check` that runs `--fix` must not be
  reused as a CI step.
- First CI run on an existing codebase: run the lint/type/test commands locally
  first. Enabling gates on a never-linted repo fails hard; land a cleanup commit
  (or hand that off to the relevant skill) before flipping the gate on.

### 2. Author the quality-gate workflow

Create `.github/workflows/ci.yml`. Full annotated template with the coverage and
aggregator jobs wired in: [references/ci-workflow-template.md](references/ci-workflow-template.md).
The load-bearing choices:

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
  merge_group:          # without this, merge-queue validation silently never reports

permissions:
  contents: read        # job-level blocks widen this only where needed

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

- **Jobs**: `lint` (ruff check + format --check), `typecheck` (whichever checker the
  repo configures), `test` (pytest across the matrix). Two valid orderings — pick
  one and say why: all three in parallel (fastest wall-clock feedback) or
  `test: needs: lint` (a 10-second lint failure skips the expensive matrix; slower
  feedback when lint passes). Parallel is the safer default for small suites.
- **Environment**: `astral-sh/setup-uv` with `enable-cache: true` and a
  `python-version: ${{ matrix.python-version }}` input — no separate
  `actions/setup-python` needed. Install with `uv sync --locked --group dev`, run
  tools with `uv run <tool>`. (No uv? `actions/setup-python@v7` with `cache: pip`
  plus `pip install -e . --group dev` (pip >= 25.1 reads PEP 735 groups) and direct tool commands is the fallback; state it
  once and move on.)
- **Matrix**: every version in `requires-python`, quoted — `['3.11', '3.12',
  '3.13', '3.14']` (3.10 reaches EOL 2026-10; 3.15 ships 2026-10-01). Unquoted `3.10` is YAML for the float `3.1`. Decision rule for
  `fail-fast`: `false` when you want full cross-version signal (default here),
  `true` only for quick PR loops where first-failure is enough. OS axis only if the
  package does platform-dependent work; each axis multiplies billed minutes
  (hard cap 256 jobs per workflow run).
- Pin every action to a full commit SHA (step 6) from the first draft, not as a
  later pass.

### 3. Wire coverage through the matrix (workflow side only)

If the repo measures coverage, per-leg gating is wrong: a leg that skips
version-specific code fails even when combined coverage is fine.

- Each matrix leg runs `pytest --cov --cov-fail-under=0` with
  `COVERAGE_FILE=.coverage.py${{ matrix.python-version }}` (pytest-cov writes one
  `.coverage` per leg and applies the config's `fail_under` per leg unless told
  not to), then uploads it as an artifact: unique name including the matrix
  values, and `include-hidden-files: true` because `.coverage.*` files are hidden.
- A `coverage` job (`needs: test`) downloads all legs, runs `uv run coverage
  combine` and `uv run coverage report`. The threshold *value* and
  `relative_files = true` (required for cross-runner combining) live in the repo's
  coverage config — python-testing territory; this skill only places the gate in
  the combine job.
- Uploading to an external service (Codecov etc.)? Upload from the combine job or
  one canonical leg — every-leg uploads produce duplicate/conflicting reports.

### 4. Add the aggregator job — the only required check

Matrix legs and job names change; branch settings do not follow them. Gate on one
stable job:

```yaml
  all-checks-passed:
    runs-on: ubuntu-latest
    needs: [lint, typecheck, test, coverage]
    if: always()        # without this the job is SKIPPED when a dep fails — and skipped counts as success
    steps:
      - name: Fail if any needed job did not succeed
        run: |
          if [[ "${{ contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled') || contains(needs.*.result, 'skipped') }}" == "true" ]]; then
            echo "::error::A required job failed, was cancelled, or was skipped."
            exit 1
          fi
          echo "All checks passed."
```

- `skipped` is in the test on purpose: a misconfigured `if:` on a dependency
  then surfaces instead of silently passing. Only if some jobs are
  intentionally path-filtered do you drop it — and document why (the reference
  has the path-filter variant).
- Keep the job name stable; renaming it means updating branch settings in the
  same PR or nothing merges.

### 5. Make it required — rulesets or branch protection

Run the workflow once first (push a branch / open a test PR): checks only appear in
the required-checks picker after they have reported at least once.

Prefer **rulesets** (layerable, target tags too, org-level, "Evaluate" preview
mode, fine-grained bypass actors); classic branch protection is fine for a single
simple repo. Configure via API to avoid drift — classic:

```bash
# --field/-F send strings (and coerce bools/ints), never nested objects — give the
# API a JSON body instead.
gh api repos/{owner}/{repo}/branches/main/protection --method PUT --input - <<'JSON'
{ "required_status_checks": { "strict": true, "contexts": ["all-checks-passed"] },
  "enforce_admins": true,
  "required_pull_request_reviews": { "required_approving_review_count": 1, "dismiss_stale_reviews": true },
  "restrictions": null }
JSON
```

- Mark **only** `all-checks-passed` as required. Individual matrix legs as
  required checks stall every PR the moment the matrix changes ("waiting for
  status to be reported").
- Enable "do not allow bypassing" / keep `enforce_admins` on — otherwise an admin
  (or an agent holding an admin token) merges past every check.
- `strict: true` (branch must be up to date) on a busy main creates a rebase
  treadmill; a merge queue is the structural fix. With a merge queue, the
  workflow **must** trigger on `merge_group`, and required checks are validated
  at queue time.
- Tag protection (blocking re-tagging of releases) is a ruleset feature; add a
  tag ruleset when the repo publishes artifacts.

Ruleset JSON, merge-queue specifics, and a diagnostic playbook for "PR is green
but won't merge": [references/required-checks-and-rulesets.md](references/required-checks-and-rulesets.md).

### 6. Harden the workflows

Details, rationale, and incident history: [references/workflow-hardening.md](references/workflow-hardening.md).

- **SHA-pin every action** — mutable tags get repointed (the 2025 tj-actions
  compromise shipped malicious code to every `@v` consumer). Resolve tags:

  ```bash
  git ls-remote https://github.com/astral-sh/setup-uv refs/tags/v10\*
  # the `^{}` line is the commit SHA for annotated tags — pin that one
  ```

  Format: `uses: owner/action@<40-hex-sha>  # v10.0.1` — keep the version comment;
  note `astral-sh/setup-uv` deleted its floating major/minor tags at 8.0.0, so
  `@v10` does not resolve at all — only full versions or SHAs do;
  update tooling and humans both key off it.
- **Minimal `GITHUB_TOKEN`**: workflow-level `permissions: contents: read`,
  job-level additions only where needed. Never rely on the repo-wide default.
- **Static-analyze the workflows** with zizmor (template injection, dangerous
  triggers, excessive permissions), pinned:

  ```bash
  uvx zizmor==1.30.1 .github/workflows/
  ```

  Check https://github.com/zizmorcore/zizmor for the current release and bump the
  pin deliberately. actionlint (PyPI: `actionlint-py`, pin the release you
  verify) additionally catches structural/syntax errors a formatter won't.
- **Trust boundaries**: avoid `pull_request_target` unless you fully understand
  it — combined with checkout of PR code or cache read/write it is a live secret
  exfiltration and cache-poisoning vector. Actions caches are shared per-repo
  namespace: never cache secrets, and treat fork-PR-writable caches as untrusted
  input to later trusted jobs.
- Run `scripts/check_workflows.py` (below) to catch regressions in all of the
  above deterministically.

### 7. Verify end to end

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/check_workflows.py" --repo .        # unpinned actions, float versions, missing if: always(), ...
uvx zizmor==1.30.1 .github/workflows/               # security findings
git switch -c ci-setup && git push -u origin ci-setup
gh pr create --fill && gh pr checks --watch        # every job green, aggregator reports
```

Then confirm `all-checks-passed` is selectable and selected in the branch
rules, and — if a merge queue is on — that a queued PR actually merges.

## Output spec — what done looks like

- `.github/workflows/ci.yml`: lint + typecheck + test-matrix + (coverage) +
  `all-checks-passed`, triggers include `pull_request` and `merge_group`,
  workflow-level `permissions: contents: read`, concurrency cancellation for PRs,
  every action SHA-pinned with a version comment, quoted matrix versions,
  `uv sync --locked`.
- Branch ruleset (or classic protection) on `main` requiring only
  `all-checks-passed`, admins included, stale-review dismissal on.
- `scripts/check_workflows.py` and zizmor both exit 0 on the final tree.
- A PR that ran the full gate green — and, stated in the PR description, what the
  gate enforces and that job renames must update branch settings in the same PR.

## Failure modes & gotchas

| Symptom / risk | Cause & fix |
| --- | --- |
| PR "waiting for status to be reported" forever | Required check bound to a renamed/removed job or matrix leg. Gate on the aggregator; update settings and job name in the same PR. |
| Aggregator green while jobs failed | Missing `if: always()` — the job was skipped, and **skipped required checks count as success**. The explicit result check is load-bearing. |
| Merge queue stuck though PR checks passed | Workflow lacks the `merge_group` trigger, so the required check never reports at queue time. |
| Matrix runs Python 3.1 | Unquoted `3.10` parsed as float. Quote every version. |
| One failure cancels all matrix legs | `fail-fast` defaults to `true`; set `false` when debugging or when full cross-version signal matters. |
| Coverage fails on one leg, fine overall | Per-leg threshold enforcement. Combine first, gate once, in the combine job. |
| Required check can't be selected in settings | It has never run. Trigger the workflow once (push/PR), then select it. |
| Merges blocked though everything passed | Duplicate job names across workflow files make the check context ambiguous — keep job names unique repo-wide. |
| CI passes after an agent's PR, gate is weaker | Review workflow diffs for `\|\| true`, deleted steps, loosened triggers, edited thresholds. Server-side required checks + admin enforcement are the only layer a local agent cannot self-modify around; CODEOWNERS on `.github/` (supply-chain skill) adds review. |
| Workflow didn't trigger after a bot push/tag | Events created with the default `GITHUB_TOKEN` do not start new workflow runs — chaining needs a GitHub App token or PAT (python-release territory). |
| Format check fails right after a Ruff release | Tool versions must come from the lockfile (`uv sync --locked`), so CI and local runs use identical versions — never `pip install ruff` unpinned in a workflow step. |
| Cache poisoning via fork PRs | `pull_request_target` + cache write is an escalation path. Since 2026-06-26 untrusted triggers (`pull_request_target`, `issue_comment`, fork `workflow_run`) get a read-only cache token for default-branch scopes — treat that as the floor and still design as if fork-writable caches are hostile. |

## Bundled resources

- [references/ci-workflow-template.md](references/ci-workflow-template.md) —
  complete annotated `ci.yml` (matrix, coverage combine, aggregator) plus
  variants: `needs:`-chained jobs, path-filtered aggregator, dynamic matrix.
- [references/required-checks-and-rulesets.md](references/required-checks-and-rulesets.md) —
  aggregator pattern options, rulesets vs classic protection, `gh api` recipes,
  merge queues, tag rulesets, blocked-merge diagnostic playbook.
- [references/workflow-hardening.md](references/workflow-hardening.md) — SHA
  pinning (and the Dependabot-alerts tradeoff), `GITHUB_TOKEN` scoping, zizmor
  and actionlint usage, `pull_request_target` and cache trust boundaries.
- `scripts/check_workflows.py` — read-only hygiene scanner for
  `.github/workflows/`; non-zero exit on findings, one machine-readable line per
  finding. Run it in step 7 and after any workflow edit.
