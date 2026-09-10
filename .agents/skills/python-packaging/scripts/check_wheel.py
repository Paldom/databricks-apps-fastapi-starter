#!/usr/bin/env python3
"""Verify built Python distribution artifacts (wheel + sdist) in a dist directory.

Read-only: never modifies the project or the artifacts.

Checks:
  - dist dir contains at least one wheel (.whl) and one sdist (.tar.gz)
  - each wheel is a valid zip with exactly one *.dist-info holding
    METADATA, WHEEL, and RECORD
  - every py.typed found in the project source tree is present in each wheel
  - no test/doc/example directories leaked into the wheel as top-level packages
  - each sdist contains pyproject.toml and at least one .py file
  - every --expect PATH (repeatable, exact archive path) is present in each wheel

Output contract (machine-readable):
  failures ->  "ERROR <artifact>: <message>" on stderr, exit 1
  usage / IO problems -> "ERROR: <message>" on stderr, exit 2
  success  ->  "PASS: ..." summary on stdout, exit 0

Usage:
  python3 check_wheel.py [--project-root DIR] [--expect PATH]... [--no-sdist] [DIST_DIR]
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import zipfile
from pathlib import Path

LEAK_TOP_LEVELS = {
    "tests",
    "test",
    "testing",
    "docs",
    "doc",
    "examples",
    "example",
    "benchmarks",
    "scripts",
}
SOURCE_SKIP_DIRS = {
    ".git",
    ".hg",
    ".venv",
    "venv",
    ".env",
    "dist",
    "build",
    ".tox",
    ".nox",
    ".eggs",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "tests",
    "test",
    "site-packages",
}

errors: list[str] = []
infos: list[str] = []


def err(artifact: str, msg: str) -> None:
    errors.append(f"ERROR {artifact}: {msg}")


def find_source_py_typed(root: Path) -> list[str]:
    """Return wheel-relative archive paths for every py.typed in the source tree."""
    found: list[str] = []
    for p in sorted(root.rglob("py.typed")):
        rel = p.relative_to(root)
        if any(part in SOURCE_SKIP_DIRS for part in rel.parts):
            continue
        parts = rel.parts
        if parts and parts[0] == "src":
            parts = parts[1:]
        if parts:
            found.append("/".join(parts))
    return found


def wheel_top_levels(names: list[str]) -> list[str]:
    tops = set()
    for n in names:
        first = n.split("/", 1)[0]
        if first.endswith((".dist-info", ".data")) or not first:
            continue
        tops.add(first)
    return sorted(tops)


def check_wheel(path: Path, expected: list[str]) -> None:
    label = path.name
    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            if bad is not None:
                err(label, f"corrupt zip member {bad!r}")
                return
            names = zf.namelist()
    except zipfile.BadZipFile as exc:
        err(label, f"not a valid zip/wheel: {exc}")
        return

    dist_infos = sorted(
        {n.split("/", 1)[0] for n in names if n.split("/", 1)[0].endswith(".dist-info")}
    )
    if len(dist_infos) != 1:
        err(label, f"expected exactly one *.dist-info directory, found {dist_infos or 'none'}")
    else:
        di = dist_infos[0]
        for required in ("METADATA", "WHEEL", "RECORD"):
            if f"{di}/{required}" not in names:
                err(label, f"missing {di}/{required} — wheel is malformed and pip may reject it")

    tops = wheel_top_levels(names)
    infos.append(f"INFO {label}: top-level entries: {', '.join(tops) if tops else '(none)'}")
    if not tops:
        err(label, "wheel contains no importable top-level package or module")
    for leak in sorted({t.lower() for t in tops} & LEAK_TOP_LEVELS):
        err(
            label,
            f"top-level {leak!r} leaked into the wheel — constrain package discovery (src layout or packages.find)",
        )
    if len(tops) > 1:
        infos.append(
            f"INFO {label}: {len(tops)} top-level entries — fine for setuptools/hatchling, unsupported by uv_build"
        )

    for exp in expected:
        if exp not in names:
            err(label, f"expected file {exp!r} not found in wheel")


def check_sdist(path: Path) -> None:
    label = path.name
    try:
        with tarfile.open(path, "r:gz") as tf:
            names = tf.getnames()
    except (tarfile.TarError, OSError) as exc:
        err(label, f"not a valid .tar.gz sdist: {exc}")
        return
    has_pyproject = any(n.split("/")[1:] == ["pyproject.toml"] for n in names if "/" in n)
    if not has_pyproject:
        err(label, "sdist has no <root>/pyproject.toml — cannot be built by PEP 517 frontends")
    if not any(n.endswith(".py") for n in names):
        err(label, "sdist contains no .py files — source is missing from the artifact")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "dist_dir",
        nargs="?",
        default="dist",
        help="directory containing built artifacts (default: dist)",
    )
    ap.add_argument(
        "--project-root",
        default=".",
        help="project root to scan for py.typed parity (default: cwd)",
    )
    ap.add_argument(
        "--expect",
        action="append",
        default=[],
        metavar="PATH",
        help="archive path that must exist in every wheel (repeatable), e.g. my_package/py.typed",
    )
    ap.add_argument(
        "--no-sdist", action="store_true", help="do not require an sdist (wheel-only builds)"
    )
    args = ap.parse_args()

    dist = Path(args.dist_dir)
    root = Path(args.project_root)
    if not dist.is_dir():
        print(f"ERROR: dist directory not found: {dist}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"ERROR: project root not found: {root}", file=sys.stderr)
        return 2

    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if not wheels:
        err(str(dist), "no *.whl found — run `uv build` first")
    if not sdists and not args.no_sdist:
        err(
            str(dist),
            "no *.tar.gz sdist found — `uv build` produces both; pass --no-sdist if intentional",
        )

    expected = list(args.expect) + find_source_py_typed(root)
    # de-duplicate, preserve order
    expected = list(dict.fromkeys(expected))

    for whl in wheels:
        check_wheel(whl, expected)
    for sd in sdists:
        check_sdist(sd)

    for line in infos:
        print(line)
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        print(f"FAIL: {len(errors)} error(s) across {len(wheels)} wheel(s), {len(sdists)} sdist(s)")
        return 1
    checked = ", ".join(p.name for p in wheels + sdists)
    print(
        f"PASS: verified {checked or 'nothing'}"
        + (f" (required in wheel: {', '.join(expected)})" if expected else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
