# py.typed, PEP 561, and shipping types to your consumers

**Contents:** [The core rule](#the-core-rule) ·
[Three distribution methods](#three-ways-to-distribute-type-information) ·
[Making the marker survive the build](#making-the-marker-survive-the-build) ·
[Verify the artifact](#verify-the-artifact-not-the-source-tree) ·
[Consumer-side testing](#test-the-consumer-experience) ·
[Edge cases](#edge-cases) · [Sources](#sources)

## The core rule

[PEP 561](https://peps.python.org/pep-0561/): without an (empty) `py.typed`
marker file inside the import package, type checkers must treat every import
from the library as `Any`. The annotations exist in your source and do
nothing for consumers. mypy enforces this strictly (downstream users see
`error: Skipping analyzing "yourlib": module is installed, but missing
library stubs or py.typed marker`); pyright is more forgiving and may infer
from library code anyway — which is why the breakage often goes unnoticed by
pyright-using maintainers and is reported by mypy-using consumers.

The marker goes next to the package's `__init__.py`:

```
src/mypackage/
├── __init__.py
├── py.typed          # empty file — its presence is the whole signal
└── core.py
```

## Three ways to distribute type information

Per the [typing spec's distribution section](https://typing.python.org/en/latest/spec/distributing.html):

1. **Inline annotations + `py.typed`** — the default. Cheapest to maintain;
   types live next to implementation and can't drift.
2. **Bundled `.pyi` stubs** alongside the `.py` sources (plus `py.typed`) —
   for code that can't carry inline annotations: C extensions, generated code.
3. **A separate stub-only package** named `<library>-stubs` on PyPI —
   decouples stub releases from the runtime package (typeshed's naming
   convention). Layout: `mypackage-stubs/` containing `py.typed`,
   `__init__.pyi`, `core.pyi`.

Prefer option 1 unless the source physically can't carry annotations.

## Making the marker survive the build

Build backends differ on whether non-`.py` files inside a package are
packaged automatically. This is where `py.typed` silently disappears.

**setuptools** — requires explicit config:

```toml
[tool.setuptools.package-data]
mypackage = ["py.typed"]
```

(or `include_package_data = true` with the file tracked appropriately).

**hatchling** — packages the package directory's contents by default, so the
marker is usually included; force it if you have custom include rules:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/mypackage"]
```

**flit-core / poetry-core** — generally include files inside the package
directory; Poetry also supports an explicit `include = ["mypackage/py.typed"]`.

Backend defaults change between versions and custom include/exclude rules
override them — which is why the next section exists. Note that `uv init
--lib` scaffolds `py.typed` for new libraries automatically.

## Verify the artifact, not the source tree

The marker being in git proves nothing about the wheel. After every packaging
change:

```bash
uv build          # or: python -m build
python3 scripts/check_py_typed.py --package mypackage
```

The bundled script checks the source package, the newest wheel, and the
newest sdist in `dist/`, and exits non-zero with `ERROR` lines if any is
missing the marker. Manual equivalent:

```bash
unzip -l dist/*.whl | grep py.typed          # wheel
tar -tzf dist/*.tar.gz | grep py.typed       # sdist
```

The sdist matters too: some consumers and rebuilders (conda-forge, distro
packagers) build from the sdist, and a marker missing there reintroduces the
bug downstream.

## Test the consumer experience

Downstream users run both major checkers, so smoke-test the published surface
with both — regardless of which one gates your CI:

```bash
uv run mypy -c "import mypackage; reveal_type(mypackage.main_entry)"
uv run pyright --verifytypes mypackage
```

`pyright --verifytypes` is purpose-built for library authors: it reports the
percentage of the public API that is fully typed and lists every symbol with
missing or partial annotations.

If your own strict run depends on `types-*` stub packages for dependencies
(e.g. `types-requests`), pin them — stub packages version independently of
the library they describe, and an unpinned stub bump can break your CI with
no change in your code.

## Edge cases

- **Single-file modules**: PEP 561 assumes packages; a lone `module.py` can't
  carry a marker. The spec's guidance is to refactor into a package. A
  community workaround — an optional companion `<name>-stubs` package
  containing only `py.typed` — is discussed in
  [this Python Discourse thread](https://discuss.python.org/t/type-hinted-single-file-modules-empty-optional-stubs-but-for-py-typed-and-pep-561/107422);
  it works with mypy, but its handling by pyright and newer checkers is
  unconfirmed. Prefer the package refactor.
- **Namespace packages**: each distributed portion needs its own `py.typed`.
- **Partial typing**: a package that is only partly annotated may still ship
  `py.typed`; consumers then see your real annotations where present and
  inferred/`Any` elsewhere. Shipping it early is better than waiting for
  100% coverage.

## Sources

- PEP 561 — [peps.python.org/pep-0561/](https://peps.python.org/pep-0561/)
- Typing spec, distribution — [typing.python.org/en/latest/spec/distributing.html](https://typing.python.org/en/latest/spec/distributing.html)
- "Don't forget py.typed" — [dev.to/whtsky/don-t-forget-py-typed-for-your-typed-python-package-2aa3](https://dev.to/whtsky/don-t-forget-py-typed-for-your-typed-python-package-2aa3)
- Single-file modules and PEP 561 — [discuss.python.org/t/type-hinted-single-file-modules-empty-optional-stubs-but-for-py-typed-and-pep-561/107422](https://discuss.python.org/t/type-hinted-single-file-modules-empty-optional-stubs-but-for-py-typed-and-pep-561/107422)
