# Build backends, file inclusion, and migration paths

Long-form companion to the python-packaging skill. Everything here targets the
user's library repo; commands are copy-runnable there.

**Contents:**
[Decision table](#decision-table) ·
[uv_build](#uv_build) ·
[Hatchling](#hatchling) ·
[setuptools](#setuptools) ·
[py.typed and data files per backend](#pytyped-and-data-files-per-backend) ·
[Migration paths](#migration-paths) ·
[Legacy tool → uv command map](#legacy-tool--uv-command-map) ·
[Evidence notes](#evidence-notes) ·
[Sources](#sources)

## Decision table

| Situation | Backend |
| --- | --- |
| Pure-Python library, greenfield or modernization | `uv_build` — zero-config `src/` and flat discovery, strict metadata validation |
| Version must derive from git tags at build time | `hatchling` + `hatch-vcs` (uv_build has no plugin API for this; `uv-dynamic-versioning` exists but is hatchling-based) |
| C / Cython / Rust extension modules | `setuptools` (or `maturin`/`scikit-build-core` for Rust/CMake) — uv_build does not build extensions |
| Deep legacy setuptools config already working | keep `setuptools`, migrate metadata to `[project]` only |
| New project considering Poetry | `poetry-core` reads PEP 621 `[project]` since Poetry 2.0, so metadata is no longer the objection — the reason to prefer uv_build/hatchling is one toolchain for env + lock + build, not a metadata format |

`uv build` is a PEP 517 **frontend**: it invokes whatever `[build-system]`
declares (hatchling, setuptools, flit-core, …). Choosing uv as project manager
and choosing the backend are independent decisions.

## uv_build

```toml
[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"
```

- **Always keep the upper bound.** uv_build follows uv's versioning policy —
  breaking changes may arrive in minor releases (not strict SemVer) — so
  `requires = ["uv_build"]` unbounded can break builds when a new version lands.
- **Stability**: uv_build is marked Development Status 5 — Production/Stable on
  PyPI and has been the `uv init` default since mid-2025. uv overall is still
  pre-1.0. Assess risk for the backend and the tool separately.
- **Layout discovery**: expects `src/<module>/__init__.py` (preferred) or
  `./<module>/`, with `<module>` = the normalized project name
  (`my-package` → `my_package`).
- **Constraint**: modules must be declared — one by default (the normalized
  project name), several via `module-name = ["a", "b"]`, or a namespace via
  `namespace = true` (disables safety checks; prefer the explicit list). Data
  files must live under the module root. Anything the discovery cannot express
  is a setuptools/hatchling job.
- **No extension modules** (C/Cython/Rust). Silently choosing uv_build for a
  project with extensions is a dead end.

Customization lives under `[tool.uv.build-backend]`:

```toml
[tool.uv.build-backend]
module-name = "my_actual_import_name"   # dots allowed for namespace packages: "foo.bar"
module-root = ""                         # "" = flat layout; default is "src"
data = { scripts = "data/scripts" }      # extra data directories
source-include = ["docs/*.md"]           # extra files for the sdist
source-exclude = ["**/*_test.py"]
wheel-exclude = ["**/*.dev.json"]
```

Exclusions always take precedence over inclusions. To debug uv_build when it
is driven by another frontend (`pip`, `python -m build`), set
`RUST_LOG=uv=debug` (or `RUST_LOG=uv=verbose`). Known edge case: build
isolation ignores project constraints while resolving dynamic build-backend
requirements (astral-sh/uv issue #17950).

If uv detects TOML 1.1-only syntax in `pyproject.toml` it may reformat the file
and keep the original as `pyproject.toml.orig` — do not be surprised by that
artifact appearing.

## Hatchling

```toml
[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/my_package"]
```

- With `src/` layout, point the wheel target at the package as above; hatchling
  then ships everything inside that directory (including non-`.py` files such
  as `py.typed`) automatically.
- Files *outside* the package directory: `packages` is `only-include` under the
  hood and **ignores `include` patterns**, so an `include = [...]` next to it
  silently ships nothing. Either move the assets inside the package (then they
  ride along automatically) or map them explicitly:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/my_package"]

[tool.hatch.build.targets.wheel.force-include]
"assets/templates" = "my_package/templates"   # source path -> path inside the wheel
```

- Dynamic versioning from git tags is hatchling's headline feature via
  `hatch-vcs` — configuring the *release* process around it belongs to the
  python-release skill, if installed; here it is only a backend-selection input.

## setuptools

```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
my_package = ["py.typed", "data/*.json"]
```

- Constrain discovery with `where = ["src"]` (or an equivalent `include` list).
  Left unconstrained on a flat layout, auto-discovery happily packages `tests/`
  or `docs/` if they contain `__init__.py`.
- Non-`.py` files require `[tool.setuptools.package-data]` (with
  `include-package-data` defaulting appropriately when using modern setuptools);
  `MANIFEST.in` controls the *sdist* and is unnecessary for most projects once
  `package-data` is set.
- `setup.py` is still legitimately required for `ext_modules` (C extensions).
  Keep it for that single purpose and move every other field into `[project]`.

## py.typed and data files per backend

`py.typed` is an empty marker file inside the package (`src/my_package/py.typed`).
Whether to ship one, and typing strategy generally, is the python-typing skill's
domain — this table is only about getting an existing file into the wheel.
No backend ships arbitrary non-`.py` files "for free" in every configuration;
the frequent silent failure is a wheel that builds fine with the marker missing,
giving every consumer `Any` for your whole API.

| Backend | What makes `py.typed` land in the wheel |
| --- | --- |
| `uv_build` | keep it under the module root (`src/my_package/py.typed`); `uv init --lib` scaffolds it |
| `hatchling` | keep it inside the directory listed in `[tool.hatch.build.targets.wheel] packages` |
| `setuptools` | `[tool.setuptools.package-data] my_package = ["py.typed"]` |
| `poetry-core` | an `include` entry under `[tool.poetry]` |

Always confirm in the artifact: `unzip -l dist/*.whl | grep py.typed` or run the
bundled `scripts/check_wheel.py`, which fails if a source-tree `py.typed` is
absent from the wheel.

## Migration paths

### From setup.py / setup.cfg

1. Translate metadata to `[project]` (PEP 621): `name`, `version`,
   `description`, `readme`, `requires-python`, `license`, `authors`,
   `dependencies`, `classifiers`, entry points to `[project.scripts]`.
2. Set `[build-system]` per the decision table.
3. Delete `setup.py`, `setup.cfg`, `MANIFEST.in` (exception: `setup.py` kept
   solely for `ext_modules`).
4. `uv build`, then verify artifacts (skill step 8). Compare the wheel's file
   list against one built from the old configuration if in doubt.

### From Poetry

1. `uvx 'migrate-to-uv==0.12.0'` — converts `[tool.poetry.dependencies]` to
   `[project.dependencies]`, dev groups to `[dependency-groups]`, and
   `poetry.lock` to `uv.lock`. Pin the version: unpinned `uvx` runs whatever
   was most recently published, which is irreproducible and a supply-chain
   exposure; review and bump pins deliberately.
2. Verify resolution: `uv lock && uv sync`, run the test suite.
3. Switch `[build-system]` away from `poetry-core` **last**. Changing the
   backend before dependencies resolve is the classic mistake — you end up
   debugging metadata translation and backend behavior at the same time.
4. Do not leave a repo half-migrated: uv and Poetry in one repo is a known
   footgun; finish or revert.

### From requirements.txt / pip-compile

1. `uv add -r requirements.txt` (add `-c constraints.txt` if used) — populates
   `[project.dependencies]` and `uv.lock` together.
2. Move dev-only entries with `uv add --dev`.
3. Delete `requirements*.txt`. If downstream tooling still needs one,
   `uv export` emits a compatible file — generate it, never hand-maintain it.

## Legacy tool → uv command map

| Task | Legacy tool(s) | uv equivalent |
| --- | --- | --- |
| Create venv | `venv`, `virtualenv` | `uv venv` (auto-created on first project command) |
| Resolve/lock | `pip-tools`, `poetry lock` | `uv lock` → `uv.lock` |
| Install deps | `pip install -r requirements.txt` | `uv sync` |
| Run in env | manual `source .venv/bin/activate` | `uv run <cmd>` |
| Build sdist+wheel | `python -m build` | `uv build` |
| Run a tool once | `pipx run` | `uvx` |
| Install a global tool | `pipx install` | `uv tool install` |
| Export pins | `pip freeze` | `uv export` |

(Version bumping and publishing — `uv version --bump`, `uv publish` — belong to
the python-release skill, if installed.)

## Evidence notes

- Build-speed multipliers for uv_build (for example "10–35x faster than
  hatchling/setuptools") come from practitioner blog posts, not independent
  controlled benchmarks. Directionally credible; do not quote the numbers as
  established fact.
- "Hatchling is the current recommended default" reflects general packaging
  guidance predating uv_build's stabilization; inside the uv ecosystem,
  uv_build is the default for new pure-Python projects. Both statements are
  true in their contexts — present the trade-off, not a universal winner.

## Sources

- uv build backend concepts — https://docs.astral.sh/uv/concepts/build-backend/
- Building and publishing a package (uv docs) — https://docs.astral.sh/uv/guides/package/
- uv versioning policy — https://docs.astral.sh/uv/reference/policies/versioning/
- uv projects guide — https://docs.astral.sh/uv/guides/projects/
- uv_build declared stable (byteiota) — https://byteiota.com/uv-build-backend-stable-python-packaging/
- src layout vs flat layout — https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- PEP 621 (project metadata) — https://peps.python.org/pep-0621/
- PEP 735 (dependency groups) — https://peps.python.org/pep-0735/
- PEP 561 (py.typed distribution) — https://peps.python.org/pep-0561/
- validate-pyproject — https://validate-pyproject.readthedocs.io/
- migrate-to-uv — https://github.com/mkniewallner/migrate-to-uv
