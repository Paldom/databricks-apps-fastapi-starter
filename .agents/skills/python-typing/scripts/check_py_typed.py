#!/usr/bin/env python3
"""Verify a PEP 561 py.typed marker exists in the source package AND in built artifacts.

Read-only: this script never creates, modifies, or deletes anything. Build the
artifacts first (`uv build` or `python -m build`), then run:

    python3 check_py_typed.py [--package NAME] [--root DIR] [--dist DIR] [--source-only]

Checks performed:
  1. source  — <root>/src/<pkg>/py.typed or <root>/<pkg>/py.typed exists
  2. wheel   — newest *.whl in <dist> contains <pkg>/py.typed
  3. sdist   — newest *.tar.gz in <dist> contains .../<pkg>/py.typed

Output: one `OK`/`ERROR`/`WARN <check>: <detail>` line per check.
Exit codes: 0 = all checks passed, 1 = at least one ERROR, 2 = usage error.
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import zipfile
from pathlib import Path

SKIP_DIRS = {
    "tests",
    "test",
    "docs",
    "doc",
    "examples",
    "scripts",
    "tools",
    "build",
    "dist",
    "site-packages",
    "node_modules",
    "__pycache__",
}

failures = 0


def report(status: str, check: str, detail: str) -> None:
    global failures
    if status == "ERROR":
        failures += 1
    print(f"{status} {check}: {detail}")


def candidate_packages(root: Path) -> list[Path]:
    """Import packages under <root>/src/ (preferred) or <root>/, by __init__.py."""
    found: list[Path] = []
    for base in (root / "src", root):
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if (
                child.is_dir()
                and child.name not in SKIP_DIRS
                and not child.name.startswith(".")
                and (child / "__init__.py").is_file()
            ):
                found.append(child)
        if found:
            break  # src layout wins; don't mix in flat-layout lookalikes
    return found


def locate_package(root: Path, name: str | None) -> Path | None:
    if name:
        for base in (root / "src", root):
            pkg = base / name
            if (pkg / "__init__.py").is_file():
                return pkg
        report(
            "ERROR",
            "source",
            f"package {name!r} not found under {root}/src or {root} (no __init__.py)",
        )
        return None
    candidates = candidate_packages(root)
    if not candidates:
        report("ERROR", "source", f"no import package found under {root} — pass --package NAME")
        return None
    if len(candidates) > 1:
        names = ", ".join(c.name for c in candidates)
        report("ERROR", "source", f"multiple packages found ({names}) — pass --package NAME")
        return None
    return candidates[0]


def newest(dist: Path, pattern: str) -> Path | None:
    matches = sorted(dist.glob(pattern), key=lambda p: p.stat().st_mtime)
    return matches[-1] if matches else None


def contains_marker(members: list[str], pkg: str) -> bool:
    target = f"{pkg}/py.typed"
    return any(m == target or m.endswith("/" + target) for m in members)


def check_wheel(dist: Path, pkg: str) -> None:
    whl = newest(dist, "*.whl")
    if whl is None:
        report(
            "ERROR", "wheel", f"no *.whl in {dist} — run `uv build` (or `python -m build`) first"
        )
        return
    try:
        with zipfile.ZipFile(whl) as zf:
            members = zf.namelist()
    except (OSError, zipfile.BadZipFile) as exc:
        report("ERROR", "wheel", f"cannot read {whl.name}: {exc}")
        return
    if contains_marker(members, pkg):
        report("OK", "wheel", f"{whl.name} contains {pkg}/py.typed")
    else:
        report(
            "ERROR",
            "wheel",
            f"{whl.name} is missing {pkg}/py.typed — configure the build backend "
            "to include it (e.g. setuptools [tool.setuptools.package-data]) and rebuild",
        )


def check_sdist(dist: Path, pkg: str) -> None:
    sdist = newest(dist, "*.tar.gz")
    if sdist is None:
        report(
            "WARN",
            "sdist",
            f"no *.tar.gz in {dist} — skipping (sdist consumers rebuild from source)",
        )
        return
    try:
        with tarfile.open(sdist, "r:gz") as tf:
            members = tf.getnames()
    except (OSError, tarfile.TarError) as exc:
        report("ERROR", "sdist", f"cannot read {sdist.name}: {exc}")
        return
    if contains_marker(members, pkg):
        report("OK", "sdist", f"{sdist.name} contains {pkg}/py.typed")
    else:
        report(
            "ERROR",
            "sdist",
            f"{sdist.name} is missing {pkg}/py.typed — sdist rebuilders "
            "(conda-forge, distros) would ship an untyped package",
        )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--package", help="import package name (auto-detected when unambiguous)")
    ap.add_argument("--root", type=Path, default=Path.cwd(), help="project root (default: cwd)")
    ap.add_argument("--dist", type=Path, help="artifacts directory (default: <root>/dist)")
    ap.add_argument(
        "--source-only", action="store_true", help="only check the source tree, skip wheel/sdist"
    )
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        print(f"ERROR usage: --root {root} is not a directory")
        return 2
    dist = (args.dist or root / "dist").resolve()

    pkg_dir = locate_package(root, args.package)
    if pkg_dir is None:
        print(f"FAIL: {failures} error(s)")
        return 1
    pkg = pkg_dir.name

    marker = pkg_dir / "py.typed"
    if marker.is_file():
        report("OK", "source", f"{marker.relative_to(root)} exists")
    else:
        report(
            "ERROR",
            "source",
            f"{pkg_dir.relative_to(root)}/py.typed missing — create it "
            f"(empty file) so PEP 561 checkers stop treating {pkg} as Any",
        )

    if not args.source_only:
        if dist.is_dir():
            check_wheel(dist, pkg)
            check_sdist(dist, pkg)
        else:
            report(
                "ERROR",
                "dist",
                f"{dist} does not exist — run `uv build` first, or pass --source-only",
            )

    if failures:
        print(f"FAIL: {failures} error(s)")
        return 1
    print("OK: py.typed verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
