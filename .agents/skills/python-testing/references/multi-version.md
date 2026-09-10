# Multi-version testing: the uv loop, tox, and nox

Contents: [Choosing a runner](#choosing-a-runner) · [The plain uv loop](#the-plain-uv-loop) ·
[tox](#tox-declarative-ini) · [nox](#nox-python-configuration) ·
[uv-backed acceleration](#uv-backed-acceleration) ·
[Coverage across versions](#coverage-across-versions) ·
[Where CI takes over](#where-ci-takes-over) · [Sources](#sources)

The question "tox or nox or neither?" is genuinely unsettled — a live debate,
not a solved one (see the tox-vs-nox thread in astropy,
https://github.com/astropy/astropy/issues/16412). Treat it as a fit question:
match the runner to the project's complexity, don't migrate a working setup for
fashion.

## Choosing a runner

| Situation | Recommendation | Why |
| --- | --- | --- |
| Simple deps, no per-version extras, no C extensions | plain `uv run -p` loop | zero config files, uv provisions interpreters on demand |
| Complex matrix — extras, doc builds, lint envs, C extensions | tox or nox | structured isolation, named environments, per-env deps |
| Config should be Python (conditionals, dynamic sessions) | nox | `noxfile.py` is code; sessions are decorated functions |
| Team already on tox | keep tox, add `tox-uv` | free speed-up, zero config-model change |
| Many *dependency* versions (not Python versions) | CI-side dynamic matrix | see "Where CI takes over" below |

Interpreter availability is what used to make tox/nox painful: each Python in
the envlist had to pre-exist on the machine. `uv python install 3.11 3.12 3.13 3.14`
(or uv's on-demand download inside `uv run -p`) removes that class of failure
entirely.

## The plain uv loop

For a package with straightforward dependencies, a loop replaces the whole
runner layer:

```bash
for v in 3.11 3.12 3.13 3.14; do
  uv run -p "$v" --with pytest --with pytest-cov pytest || exit 1
done
```

- `|| exit 1` matters — without it the loop reports only the last version's
  status.
- Wrap it in a task runner (a `just` recipe or Makefile target) so the matrix
  is one memorable command and the version list lives in one place.
- The loop tests against the *resolved project environment* per version; if a
  dependency has no wheel for an older interpreter, the failure surfaces here
  exactly as it would for a user — that is signal, not noise.
- What you give up vs tox/nox: named auxiliary environments (docs, lint),
  per-env dependency overrides, and parallel env execution. When you start
  wanting those, switch runners instead of growing the loop.

## tox: declarative INI

```ini
# tox.ini
[tox]
envlist = py310, py311, py312, py313
isolated_build = true

[testenv]
deps =
    pytest
    pytest-cov
commands =
    pytest {posargs}
```

- `{posargs}` passes through anything after `--` (`tox -- -k parser -x`), so
  the matrix entry point still supports single-test loops.
- Keep dependency versions out of `[testenv] deps` where possible; prefer
  installing the project's own dev extras so tox and plain `uv run pytest`
  test the same pins.
- tox environments are cached in `.tox/`; a stale env after dependency changes
  is fixed with `tox -r` (recreate) — a classic "works in CI, stale locally"
  source.

## nox: Python configuration

```python
# noxfile.py
import nox

nox.options.default_venv_backend = "uv"

@nox.session(python=["3.11", "3.12", "3.13", "3.14"])
def tests(session):
    session.install(".", "pytest", "pytest-cov")
    session.run("pytest", *session.posargs)
```

- Sessions are plain Python — conditionals, version-specific deps, and dynamic
  parametrization need no plugin system.
- **Footgun:** a repo-root `.python-version` file can silently pin every nox
  session to the locally selected interpreter, so the "matrix" runs one version
  N times (https://github.com/wntrblm/nox/issues/1038). If the repo carries a
  `.python-version`, verify each session's `python --version` output the first
  time the matrix runs.

## uv-backed acceleration

Both runners can delegate environment creation to uv — the config model stays
identical, only env setup gets fast:

- tox: add `tox-uv` (`uv add --dev tox-uv`); tox picks the plugin up
  automatically.
- nox: set `nox.options.default_venv_backend = "uv"` (as above) or pass
  `--default-venv-backend uv`; install nox itself with the extra
  (`nox[uv]`) so the backend is available.

Environment creation is usually the dominant cost of a local matrix run, so
this is the highest-leverage change for an existing tox/nox setup — far cheaper
than a runner migration.

## Coverage across versions

The rule from SKILL.md step 7, in full:

1. `[tool.coverage.run]` needs `parallel = true` and `relative_files = true`
   so each leg writes its own `.coverage.<suffix>` data file instead of
   overwriting a shared one.
2. Run the matrix (loop, tox, or nox). Each version leg runs
   `pytest --cov` **without** any `fail_under` enforcement.
3. Combine once, gate once:

```bash
uv run coverage combine
uv run coverage report --fail-under=85
```

Never enforce the threshold inside a version leg: code guarded by
`sys.version_info >= (3, 13)` is legitimately unexecuted on the 3.10 leg, so a
per-leg gate fails builds for having version-specific branches at all. Only the
combined union is a meaningful number. (Same reasoning applies to uploading
coverage from every CI leg — it double-counts or conflicts; combine
deliberately.)

Under tox, "coverage is 0% / no data collected" is almost always the parallel
data files never being combined, or the project being imported from `.tox/`
site-packages while `source = ["src"]` points elsewhere — `relative_files =
true` plus a `coverage combine` step resolves both.

## Where CI takes over

This reference covers deciding and running the matrix locally. The CI half —
GitHub Actions `strategy: matrix` wiring, per-leg artifact upload, a combine
job, patch-coverage gates on PRs — is the python-ci skill's territory (if
installed). Two patterns worth knowing exist on that side so you don't rebuild
them locally:

- OS × Python matrices (e.g. 3 OSes × 4 versions) are a CI-native concern;
  locally, testing the oldest and newest supported Python catches most issues.
- Testing against many versions of a *dependency* (not of Python) is a
  CI-dynamic-matrix problem — MLflow's pattern (a central versions YAML plus a
  script that queries PyPI and samples versions, always including min/max) is
  the reference architecture there, not a local-runner concern.

## Sources

- pytest good practices (src layout, installed-package testing) —
  https://docs.pytest.org/en/stable/explanation/goodpractices.html
- tox-vs-nox live debate — https://github.com/astropy/astropy/issues/16412
- nox `.python-version` footgun — https://github.com/wntrblm/nox/issues/1038
- tox-uv — https://github.com/tox-dev/tox-uv
- nox uv backend — https://nox.thea.codes/en/stable/usage.html
- coverage.py combine mechanics — https://coverage.readthedocs.io/en/latest/cmd.html#combining-data-files
