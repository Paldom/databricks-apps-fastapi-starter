# pytest and coverage configuration in depth

**Contents:** [Config source precedence](#config-source-precedence) ·
[The pytest 9 table question](#the-pytest-9-table-question) ·
[Recommended pytest block](#recommended-pytest-block) ·
[Recommended coverage block](#recommended-coverage-block) ·
[Proving the gate](#proving-the-gate) ·
[Parallelism and combining data](#parallelism-and-combining-data) ·
[Weakly-sourced leads](#weakly-sourced-leads) · [Sources](#sources)

## Config source precedence

Both tools read exactly one config source and silently ignore the rest. Most
"my config change did nothing" reports trace back to this.

**pytest** stops at the first file that qualifies as a config file, in this
order (see https://docs.pytest.org/en/stable/reference/customize.html):

1. `pytest.toml` / `.pytest.toml` (win even if empty; pytest >= 9)
2. `pytest.ini` / `.pytest.ini` (win even if empty)
3. `pyproject.toml` (only counts with a `[tool.pytest]` or `[tool.pytest.ini_options]` table)
4. `tox.ini` (only with a `[pytest]` section)
5. `setup.cfg` (only with a `[tool:pytest]` section)

**coverage.py** reads the first of (see
https://coverage.readthedocs.io/en/latest/config.html):

1. `.coveragerc` (wins even when pyproject has `[tool.coverage.*]`)
2. `.coveragerc.toml`
3. `setup.cfg` / `tox.ini` (`[coverage:...]` sections)
4. `pyproject.toml` (`[tool.coverage.*]`)

Rule: one source per tool, preferably `pyproject.toml` for both, and delete the
losers after merging. The bundled `scripts/check_test_config.py` flags these
conflicts.

## The two pyproject tables

pytest 9.0 (2025-11-05) added a native `[tool.pytest]` table — real TOML arrays
and booleans for `addopts`/`testpaths` instead of the INI-string bridge that
`[tool.pytest.ini_options]` (pytest >= 6) provides. Rules, from
https://docs.pytest.org/en/stable/reference/customize.html:

- Use one table, never both; pick by `uv run pytest --version`.
- On pytest < 9 an unrecognized `[tool.pytest]` table produces no error. Tests
  run with default (lenient) settings and every strictness flag you thought you
  set is off — `--strict-config` cannot save you because it is itself inside the
  ignored table. `ini_options` works on every supported pytest.
- Keys are the same in both tables; only the value types differ
  (`addopts = ["-ra", "--strict-markers"]` vs `addopts = "-ra --strict-markers"`).

Also relevant when upgrading: pytest 9.x tightened config and deprecation
handling (warnings that used to pass now error), so a major-version bump can
break a previously green setup — read the release notes before bumping
`minversion`.

## Recommended pytest block

```toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config"
filterwarnings = ["error"]
# async projects, with pytest-asyncio installed:
# asyncio_mode = "auto"
```

| Setting | Why |
| --- | --- |
| `minversion` | Fails fast when an old pytest would misread newer config |
| `testpaths` | Collection doesn't wander into `build/`, `.venv/`, docs |
| `-ra` | Summary of all non-passing outcomes at the end of a run |
| `--strict-markers` | Typo'd/undeclared `@pytest.mark.*` = error, not a silently-skipped mark |
| `--strict-config` | Typo'd config keys = error |
| `filterwarnings = ["error"]` | Deprecations fail during development, not during a forced upgrade |
| `asyncio_mode = "auto"` | Drops the `@pytest.mark.asyncio` boilerplate on every async test |

`filterwarnings = ["error"]` on a legacy dependency tree produces noise from
third-party deprecations. Add targeted ignores rather than removing the gate:

```toml
filterwarnings = [
    "error",
    "ignore::DeprecationWarning:somepackage.*",
]
```

Declare markers you use so `--strict-markers` accepts them:

```toml
markers = [
    "slow: long-running tests, deselect with -m 'not slow'",
]
```

### Should `--cov` live in addopts?

Trade-off, not a rule:

- **Out of addopts** (this skill's default): single-test debugging stays fast,
  debugger breakpoints behave, and coverage is an explicit act
  (`uv run pytest --cov`). CI must remember to pass the flags.
- **In addopts**: coverage can never be forgotten; every invocation pays
  instrumentation overhead. Escape hatch for one run: `--no-cov`.

Pick one, tell the user which and why.

## Recommended coverage block

```toml
[tool.coverage.run]
source = ["src"]
branch = true
parallel = true
relative_files = true

[tool.coverage.report]
fail_under = 85
show_missing = true
skip_covered = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "raise AssertionError",
    "def __repr__",
    "if __name__ == .__main__.:",
]
```

Notes:

- `exclude_lines` entries are regexes — that is why `.__main__.` uses dots.
  Overriding `exclude_lines` replaces the default list, so re-state
  `pragma: no cover` when customizing.
- Flat layout (no `src/`): set `source = ["<pkg>"]` and add
  `omit = ["tests/*"]` so the tests themselves aren't measured.
- Threshold philosophy: 80–90 with branch coverage is the widely used band;
  100% is anti-recommended because it optimizes for line count over assertion
  quality. Tiered targets are a reasonable refinement (e.g. core logic higher
  than glue code). Whatever the number, it is a floor/regression alarm —
  "coverage tells you what you didn't test, not whether your tests are good."
- Per-PR patch/delta coverage ("changed lines need 80%, no legacy backfill")
  is a stronger merge gate than a global number, but it is enforced in CI
  services/workflows — out of scope here (python-ci skill, if installed).

## Proving the gate

pytest-cov has a documented failure mode where `--cov-fail-under` does not
produce a non-zero exit code for aggregate/multi-directory configurations
depending on report options, and internal rounding could pass e.g. 66.66% against a
67 requirement. pytest-cov 7.1.0 (2026-03-21) made the total consistent regardless
of reporting settings — still demonstrate the gate once per repo.
A gate that has never been seen to fail must be treated as not wired up.

Demonstration procedure (also the acceptance test after any config change):

```bash
uv run pytest --cov --cov-fail-under=100 -q; echo "exit=$?"
```

- Non-zero exit (and coverage below 100): gate works, restore the real
  threshold.
- Zero exit while coverage is below the bar: split measurement from gating —

```bash
uv run pytest --cov
uv run coverage report --fail-under=85
```

The standalone `coverage report --fail-under` exit code is reliable, and the
split has a second benefit: it is the same shape you need for combining data
from multiple runs (below).

## Parallelism and combining data

**pytest-xdist** (`pytest -n auto`) splits tests across workers, each writing
its own data file. Requirements for coverage to survive this:

- `[tool.coverage.run] parallel = true` — data files get unique suffixes
  (`.coverage.<host>.<pid>.<random>`) instead of clobbering each other.
- `relative_files = true` — paths recorded relative to the repo root so data
  from different working directories/runners lines up.
- Subprocesses spawned *by tests* (`subprocess`, `multiprocessing`) are not
  measured unless coverage is told to patch them: `[tool.coverage.run]
  patch = ["subprocess"]` (coverage >= 7.10; pytest-cov 7.0 dropped its own
  subprocess support) — see https://coverage.readthedocs.io/en/latest/subprocess.html.

Symptom of getting this wrong: coverage reports 0% or "no data collected"
under `-n auto` while a serial run looks fine.

**Combining across runs** (multiple Python versions, unit vs integration):

```bash
uv run coverage combine          # merges .coverage.* into .coverage
uv run coverage report --fail-under=85
```

Enforce the threshold once, on the combined data. Enforcing inside each leg
fails versions that legitimately skip version-specific branches. Shipping the
per-leg data files to a combine job in CI is python-ci territory.

A conflicting-advice note: some setups use `coverage run -m pytest` instead of
`pytest --cov` (plugin-loading order arguments); guidance for xdist users is
the opposite — prefer `pytest -n auto --cov`. Pick based on whether you use
xdist; don't mix both invocation styles in one repo.

## Weakly-sourced leads

Verify before acting; both were single-sourced in the research behind this
skill:

- **Python 3.14+ `sys.monitoring` core**: reported to silently break per-test
  ("dynamic context") coverage tracking, with `COVERAGE_CORE=ctrace` as the
  fallback. Check the coverage.py changelog
  (https://coverage.readthedocs.io/en/latest/changes.html) if per-test
  contexts misbehave on 3.14+.
- OpenSSF-badge-driven coverage floors appearing as external requirements —
  observed once, not an established pattern.

## Sources

- pytest configuration reference — https://docs.pytest.org/en/stable/reference/customize.html
- pytest good practices (src layout, importmode) — https://docs.pytest.org/en/stable/explanation/goodpractices.html
- pytest changelog — https://docs.pytest.org/en/stable/changelog.html
- coverage.py config reference — https://coverage.readthedocs.io/en/latest/config.html
- coverage.py subprocess measurement — https://coverage.readthedocs.io/en/latest/subprocess.html
- pytest-cov docs — https://pytest-cov.readthedocs.io/
- pytest-cov exit-code report — https://stackoverflow.com/questions/79815717/why-doesnt-pytest-cov-fail-with-a-non-zero-exit-code-when-code-coverage-thresho
- Modern Python CI with coverage (combine-then-gate walkthrough) — https://danielnouri.org/notes/2025/11/03/modern-python-ci-with-coverage-in-2025/
