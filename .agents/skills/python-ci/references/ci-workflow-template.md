# CI workflow template (Python + uv)

**Contents:** [Placeholder convention](#placeholder-convention) ·
[Complete ci.yml](#complete-ciyml) · [Resolving SHAs](#resolving-shas-for-pins) ·
[setup-uv and caching notes](#setup-uv-and-caching-notes) ·
[Variant: lint gates the matrix](#variant-lint-gates-the-matrix) ·
[Variant: path-filtered jobs and the aggregator](#variant-path-filtered-jobs-and-the-aggregator) ·
[Variant: dynamic matrix](#variant-dynamic-matrix) ·
[Sources](#sources)

## Placeholder convention

Every `uses:` below is written `owner/action@<pin-sha>  # vX.Y.Z`. Before
committing, replace each `<pin-sha>` with the full 40-character commit SHA of the
release you chose (see [Resolving SHAs](#resolving-shas-for-pins)) and put the real
version in the comment. Do not commit tags (`@v4`) — mutable tags are the
supply-chain hole SHA pinning closes. Adjust the matrix to the repo's
`requires-python`, and the tool commands to what `pyproject.toml` actually
configures.

## Complete ci.yml

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
  # Required when a merge queue is enabled: required checks re-validate on the
  # speculative merge commit. Without this trigger the queue waits forever.
  merge_group:

# Least privilege for every job; widen per-job only where needed.
permissions:
  contents: read

# Cancel superseded runs on PRs; let main/merge_group runs finish.
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<pin-sha>  # vX.Y.Z
      - uses: astral-sh/setup-uv@<pin-sha>  # vX.Y.Z
        with:
          enable-cache: true
      - run: uv sync --locked --group dev
      # Check mode only. CI verifies; it never rewrites code.
      - run: uv run ruff check --output-format=github .
      - run: uv run ruff format --check .

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<pin-sha>  # vX.Y.Z
      - uses: astral-sh/setup-uv@<pin-sha>  # vX.Y.Z
        with:
          enable-cache: true
      - run: uv sync --locked --group dev
      # Use the checker the repo configures: mypy, pyright, or ty.
      - run: uv run mypy src/

  test:
    runs-on: ubuntu-latest
    strategy:
      # false = full cross-version signal (one leg failing doesn't cancel the rest).
      # Flip to true only for quick PR loops where first-failure is enough.
      fail-fast: false
      matrix:
        # QUOTED strings. Unquoted 3.10 is YAML for the float 3.1.
        python-version: ['3.11', '3.12', '3.13', '3.14']   # = requires-python; 3.10 EOL 2026-10
    steps:
      - uses: actions/checkout@<pin-sha>  # vX.Y.Z
      - uses: astral-sh/setup-uv@<pin-sha>  # vX.Y.Z
        with:
          python-version: ${{ matrix.python-version }}
          enable-cache: true
      - run: uv sync --locked --group dev
      # pytest-cov manages coverage's `parallel` itself and writes ONE `.coverage`
      # per leg, so give each leg its own file name or the download step's merge
      # keeps only the last leg. `--cov-fail-under=0` disables the per-leg gate
      # (pytest-cov otherwise applies the config's fail_under to this leg alone).
      - run: uv run pytest --cov --cov-fail-under=0
        env:
          COVERAGE_FILE: .coverage.py${{ matrix.python-version }}
      # Artifact name must include matrix values or legs overwrite each other.
      # .coverage.* files are hidden -> include-hidden-files.
      - uses: actions/upload-artifact@<pin-sha>  # vX.Y.Z
        with:
          name: coverage-${{ matrix.python-version }}
          path: .coverage.*
          include-hidden-files: true
          if-no-files-found: error

  coverage:
    runs-on: ubuntu-latest
    needs: [test]
    steps:
      - uses: actions/checkout@<pin-sha>  # vX.Y.Z
      - uses: astral-sh/setup-uv@<pin-sha>  # vX.Y.Z
        with:
          enable-cache: true
      - run: uv sync --locked --group dev
      - uses: actions/download-artifact@<pin-sha>  # vX.Y.Z
        with:
          pattern: coverage-*
          merge-multiple: true
      # Combine ALL legs, then gate ONCE. Per-leg gating fails legs that
      # legitimately skip version-specific code. The fail_under value and
      # relative_files=true live in the repo's coverage config (python-testing
      # skill territory), not here.
      - run: uv run coverage combine
      - run: uv run coverage report
      # External upload (optional): do it here, once — not from every leg.

  # THE required check. Mark only this job as required in branch rules.
  all-checks-passed:
    runs-on: ubuntu-latest
    needs: [lint, typecheck, test, coverage]
    # Load-bearing: without always(), a failed dependency SKIPS this job,
    # and a skipped required check counts as SUCCESS -> the PR merges unvalidated.
    if: always()
    steps:
      - name: Fail if any needed job did not succeed
        run: |
          if [[ "${{ contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled') || contains(needs.*.result, 'skipped') }}" == "true" ]]; then
            echo "::error::A required job failed, was cancelled, or was skipped."
            exit 1
          fi
          echo "All checks passed."
```

Notes:

- The `skipped` clause assumes no job in `needs:` is ever intentionally skipped.
  If some are (path filters, conditional jobs), drop `skipped` and use the
  [path-filtered variant](#variant-path-filtered-jobs-and-the-aggregator).
- No-uv fallback: replace setup-uv with `actions/setup-python` (`cache: pip`),
  `pip install -e '.[dev]'`, and drop the `uv run` prefixes. Same shape otherwise.
- `--output-format=github` makes ruff findings appear as inline PR annotations.

## Resolving SHAs for pins

```bash
# List tag refs; for annotated tags the '^{}' line is the actual commit — pin that.
git ls-remote https://github.com/actions/checkout 'refs/tags/v4*'
git ls-remote https://github.com/astral-sh/setup-uv 'refs/tags/v5*'

# Or via the API (dereference annotated tags if object.type == "tag"):
gh api repos/actions/checkout/git/ref/tags/v4.2.2 --jq '.object | .type + " " + .sha'
```

Keep the human-readable version as a trailing comment (`# v4.2.2`): update
tooling uses it to know what the SHA means, and reviewers can audit bumps.
Trade-off to know: Dependabot *version updates* can still bump SHA-pinned actions
(keeping the comment in sync), but Dependabot *alerts* historically only fired for
tag-pinned actions — pinning trades some alert visibility for immutability. The
python-supply-chain skill owns the Dependabot side.

## setup-uv and caching notes

- `astral-sh/setup-uv` with a `python-version` input installs the interpreter too;
  a separate `actions/setup-python` step is unnecessary.
- `enable-cache: true` caches uv's download cache keyed off the lockfile;
  `uv sync --locked` then rebuilds the venv in seconds and **fails if
  `uv.lock` is out of date with `pyproject.toml`** — the correct CI behavior.
  Never `uv lock` in CI: a lockfile regenerated in the runner evaporates after
  the run and masks the fact that the committed one is stale.
- For non-uv custom caching, `actions/cache` keys should hash the lockfile
  (`${{ runner.os }}-pip-${{ hashFiles('**/uv.lock') }}`) and always define
  `restore-keys:` prefixes — over-specific keys miss on every run.
- Caches are shared within the repo's namespace and are a trust boundary, not
  just a speed lever: see
  [workflow-hardening.md](workflow-hardening.md).

## Variant: lint gates the matrix

Cheap-fails-first: a 10-second ruff failure prevents 4+ matrix legs from ever
starting.

```yaml
  test:
    needs: [lint, typecheck]
    # ...same as above
```

Trade-off: when lint passes (the common case), test results arrive one job-length
later. Parallel jobs give the fastest feedback; `needs:` chains save minutes on
repos with big matrices or high push volume. Both are defensible — pick per repo
and leave a comment saying why.

## Variant: path-filtered jobs and the aggregator

When jobs are skipped on purpose (e.g. `dorny/paths-filter` skipping tests on
docs-only changes), a skipped result is expected and must not fail the gate — but
then a *misconfigured* skip also passes. Make the aggregator distinguish the two
by consulting the filter output:

```yaml
  all-checks-passed:
    runs-on: ubuntu-latest
    needs: [changes, test]
    if: always()
    steps:
      - run: |
          # The filter job itself must have succeeded, and only an explicit
          # "false" may skip the gate — an empty output (filter failed/skipped)
          # is not "no changes".
          if [[ "${{ needs.changes.result }}" != "success" ]]; then
            echo "::error::Change detection did not succeed."; exit 1
          fi
          if [[ "${{ needs.changes.outputs.code }}" == "false" ]]; then
            echo "No relevant changes; passing."; exit 0
          fi
          if [[ "${{ needs.test.result }}" == "success" ]]; then
            exit 0
          fi
          echo "::error::Tests failed, were cancelled, or were skipped unexpectedly."
          exit 1
```

An alternative that avoids adding to the critical path: a job that is skipped
unless something failed (`if: cancelled() || contains(needs.*.result, 'failure') ||
contains(needs.*.result, 'cancelled')`) — it exploits skipped-counts-as-success
instead of fighting it. Both patterns are documented with trade-offs in
[required-checks-and-rulesets.md](required-checks-and-rulesets.md).

## Variant: dynamic matrix

Monorepos / workspaces: emit the matrix as JSON from an upstream job so adding a
package never requires a workflow edit (and required checks never change name,
because the aggregator is the check):

```yaml
  prepare:
    runs-on: ubuntu-latest
    outputs:
      packages: ${{ steps.emit.outputs.packages }}
    steps:
      - uses: actions/checkout@<pin-sha>  # vX.Y.Z
      - id: emit
        run: echo "packages=$(python3 -c 'import tomllib,json;print(json.dumps(tomllib.load(open("pyproject.toml","rb"))["tool"]["uv"]["workspace"]["members"]))')" >> "$GITHUB_OUTPUT"

  test:
    needs: [prepare]
    strategy:
      matrix:
        package: ${{ fromJSON(needs.prepare.outputs.packages) }}
    runs-on: ubuntu-latest
    steps:
      # checkout + setup-uv as above
      - run: uv run --package ${{ matrix.package }} pytest
```

You cannot put an `if:` on a matrix leg — omit unwanted entries from the emitted
JSON instead. Matrix hard cap: 256 jobs per workflow run.

## Sources

- Workflow syntax (matrix, concurrency, permissions):
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- astral-sh/setup-uv (caching, python-version input): https://github.com/astral-sh/setup-uv
- Dependency caching concepts: https://docs.github.com/en/actions/concepts/workflows-and-actions/dependency-caching
- Dynamic matrix fan-out: https://devopsdirective.com/posts/2025/08/advanced-github-actions-matrix/
- Path filtering: https://github.com/dorny/paths-filter
