# Strict mode and the gradual-adoption ratchet

**Contents:** [What strict actually enables](#what-strict-actually-enables) ·
[The ratchet, stage by stage](#the-ratchet-stage-by-stage) ·
[mypy ratchet config](#mypy-ratchet-config) ·
[pyright strict islands](#pyright-strict-islands) ·
[Suppression hygiene](#suppression-hygiene) ·
[Composability traps](#composability-traps) ·
[Structural alternatives](#structural-alternatives-ty-and-pyrefly) · [Sources](#sources)

## What strict actually enables

mypy `strict = true` is a bundle of individual flags (per the
[mypy config docs](https://mypy.readthedocs.io/en/stable/config_file.html)):
`disallow_untyped_defs`, `disallow_incomplete_defs`, `disallow_untyped_calls`,
`disallow_any_generics`, `disallow_untyped_decorators`, `check_untyped_defs`,
`no_implicit_optional`, `warn_redundant_casts`, `warn_return_any`,
`warn_unused_ignores`, `strict_equality` — as of mypy 1.x; the bundle changes
across releases (mypy 2.0 also flipped `local_partial_types` and `strict_bytes`
on globally), so confirm the current list with `mypy --help`. Knowing the
components matters because the ratchet turns them on one at a time.

pyright has four `typeCheckingMode` levels — `off` / `basic` / `standard`
(default) / `strict` — and its strict is generally tighter than mypy's.
Remember pyright checks unannotated code even in `standard`, so a legacy
codebase jumping straight to pyright `strict` floods harder than the same
jump in mypy.

## The ratchet, stage by stage

Big-bang strict on an existing codebase reliably produces hundreds of errors
and a demoralized team. Tighten one dimension at a time; per-module overrides
keep new code strict while legacy code is exempted rather than fixed at once:

1. **Baseline honestly.** Enable the checker permissively — but for mypy set
   `check_untyped_defs = true` immediately, or the run is skipping every
   unannotated function body and the green result is a lie.
2. **Fix high-signal errors only** — real bugs the baseline surfaces.
3. **Optional-correctness first** — `no_implicit_optional` plus strict
   optional checking is the single biggest ROI step; most real bugs live in
   `None` handling.
4. **Require annotations** — `disallow_untyped_defs` +
   `disallow_incomplete_defs`, usually per-module as code gets touched.
5. **Strict islands** — full `strict = true` for new/core modules while
   legacy modules carry explicit exemptions.
6. **Global strict** — flip the global flag, keep a shrinking exemption list.

The invariant at every stage: **the exemption list only shrinks**. Treat each
override block as recorded debt with an owner, and delete entries as modules
are migrated. If the list grows, the ratchet is broken.

## mypy ratchet config

```toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_unused_ignores = true
# plugins = ["pydantic.mypy"]        # if pydantic is in play

# Legacy code: exempt wholesale until migrated (works reliably)
[[tool.mypy.overrides]]
module = ["myapp.legacy.*", "myapp.migrations.*"]
ignore_errors = true

# Tests often relax annotation requirements without going untyped
[[tool.mypy.overrides]]
module = ["tests.*"]
disallow_untyped_defs = false

# Third-party deps that ship no py.typed and have no types-* stubs
[[tool.mypy.overrides]]
module = ["some_untyped_lib.*"]
ignore_missing_imports = true
```

## pyright strict islands

pyright inverts the model: a permissive base with an explicit array of strict
directories, expanded as migration proceeds.

```toml
[tool.pyright]
include = ["src", "tests"]
exclude = ["**/legacy"]                              # added on top of pyright's defaults
typeCheckingMode = "standard"                        # base level while migrating
strict = ["src/myapp/core", "src/myapp/api"]         # strict islands, grow this list
pythonVersion = "3.10"
reportMissingTypeStubs = "warning"                   # strict's noisiest rule, downgraded
```

## Suppression hygiene

- Always scope ignores to an error code — `# type: ignore[arg-type]` (mypy),
  `# pyright: ignore[reportArgumentType]` — never a bare `# type: ignore`,
  which silences every future error on that line.
- Keep the rot detectors on: `warn_unused_ignores = true` (mypy) and
  `reportUnnecessaryTypeIgnoreComment = "error"` (pyright) make stale
  suppressions fail the run, so debt can't accumulate invisibly.
- Prefer a per-module override block over sprinkling tens of inline ignores
  in one file — one visible config entry is easier to track and delete.
- `typing.cast` and `Any` are suppressions too; grep for them during reviews.

## Composability traps

- **mypy [#11401](https://github.com/python/mypy/issues/11401)** ("strict is
  incompatible with per-module configuration"): with global `strict = true`
  you cannot cleanly *downgrade individual strict components* per module in
  every case. Per-module `ignore_errors = true` and flipping specific named
  flags (as above) work; expecting `strict = false` in an override to undo the
  bundle does not.
- **pyright [#601](https://github.com/microsoft/pyright/issues/601)**: under
  `typeCheckingMode = "strict"` individual rules cannot be downgraded below
  the strict floor in that scope — which is exactly why the
  standard-base-plus-strict-array pattern exists.
- Overrides silence, they don't migrate: an `ignore_errors` module is
  unchecked entirely — worse than permissive checking. Keep islands small and
  migration active.

## Structural alternatives (ty and Pyrefly)

Two newer checkers attack the same pain structurally instead of procedurally:

- **ty's gradual guarantee** — loosening or removing annotations never introduces new errors (adding precision may reveal real ones)
  elsewhere, eliminating the "annotated one function, broke ten call sites"
  cascade. Makes file-by-file adoption genuinely safe, at beta-maturity cost.
- **Pyrefly's `suppress`** — bulk-inserts suppression comments across legacy
  code, letting aggressive inference turn on immediately with debt paid down
  later — the ratchet run in reverse.

Both are worth watching; neither has a plugin system, so plugin-dependent
stacks (Django/SQLAlchemy/Pydantic-via-mypy) can't migrate yet.

## Sources

- mypy config reference — [mypy.readthedocs.io/en/stable/config_file.html](https://mypy.readthedocs.io/en/stable/config_file.html)
- mypy strict how-to — [pydevtools.com/handbook/how-to/how-to-configure-mypy-strict-mode/](https://pydevtools.com/handbook/how-to/how-to-configure-mypy-strict-mode/)
- Strategic gradual-typing guide — [medium.com/@tihomir.manushev/a-strategic-guide-to-gradual-typing-in-python-49ac85f6dbdd](https://medium.com/@tihomir.manushev/a-strategic-guide-to-gradual-typing-in-python-49ac85f6dbdd)
- Ratchet wins write-up — [medium.com/@sparknp1/7-gradual-typing-wins-in-python-494fe14be587](https://medium.com/@sparknp1/7-gradual-typing-wins-in-python-494fe14be587)
- mypy #11401 — [github.com/python/mypy/issues/11401](https://github.com/python/mypy/issues/11401)
- pyright #601 — [github.com/microsoft/pyright/issues/601](https://github.com/microsoft/pyright/issues/601)
