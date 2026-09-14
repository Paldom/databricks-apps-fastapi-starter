#!/usr/bin/env python3
"""Read-only sanity checker for a repo's Ruff lint/format configuration.

Detects the footguns that most often bite Ruff setups and migrations:
leftover Black/Flake8/isort configs, reliance on Ruff's (version-dependent) default rule set,
E501 double-reporting, formatter-conflicting rules, select = ["ALL"],
missing target-version, deprecated top-level lint keys, and
per-file-ignores patterns that match no files.

Usage:
    python3 check_ruff_config.py [--root PATH] [--strict]

Never modifies any file. Output is machine-readable, one finding per line:
    ERROR <file>: <message>
    WARN  <file>: <message>

Exit codes: 0 = clean (warnings allowed unless --strict), 1 = findings,
2 = environment/usage problem (e.g. Python < 3.11, missing pyproject.toml).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    print("ERROR environment: Python 3.11+ required (tomllib)", file=sys.stderr)
    sys.exit(2)

# Lint rules that fight `ruff format` (docs.astral.sh/ruff/formatter/#conflicting-lint-rules).
# W191/E111/E114/E117 also conflict but are preview-only rules — a plain
# select = ["E", "W"] does not enable them, so warning on them would be noise.
FORMATTER_CONFLICTS = (  # https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules (2026-09)
    "COM812",
    "COM819",
    "Q000",
    "Q001",
    "Q002",
    "Q003",
    "Q004",
    "W191",
    "E111",
    "E114",
    "E117",
    "D203",
    "D206",
    "D300",
)  # ISC001 is fine with the formatter; ISC002 conflicts only without ISC001 + allow-multiline=false
LEGACY_TOOLS = ("black", "flake8", "isort", "pyupgrade", "autoflake")
# Lint settings that belong under [tool.ruff.lint], not top-level [tool.ruff]
DEPRECATED_TOP_LEVEL = (
    "select",
    "extend-select",
    "ignore",
    "extend-ignore",
    "per-file-ignores",
    "fixable",
    "unfixable",
    "external",
)

findings: list[tuple[str, str, str]] = []  # (level, file, message)


def err(where: str, msg: str) -> None:
    findings.append(("ERROR", where, msg))


def warn(where: str, msg: str) -> None:
    findings.append(("WARN ", where, msg))


def _split_code(code: str) -> tuple[str, str]:
    """Split 'ISC001' -> ('ISC', '001'); 'E5' -> ('E', '5')."""
    m = re.match(r"^([A-Z]+)([0-9]*)$", code)
    return (m.group(1), m.group(2)) if m else (code, "")


def selected(code: str, select: list[str]) -> bool:
    """True if `select` turns on rule `code`, using Ruff's selector semantics.

    A selector matches when its alphabetic linter prefix equals the code's
    (so "I" matches I001 but NOT ISC001, "C" matches C4xx/C9xx but NOT COM812)
    and its digit part is a prefix of the code's digits.
    """
    if "ALL" in select:
        return True
    code_alpha, code_digits = _split_code(code)
    for sel in select:
        sel_alpha, sel_digits = _split_code(sel.strip())
        if sel_alpha == code_alpha and code_digits.startswith(sel_digits):
            return True
    return False


def check_legacy_remnants(root: Path, pyproject: dict) -> None:
    for name in (".flake8", ".isort.cfg"):
        if (root / name).is_file():
            err(
                name,
                "legacy config file present — Ruff never reads it; translate to [tool.ruff*] and delete",
            )
    for name in ("setup.cfg", "tox.ini"):
        p = root / name
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for section in ("[flake8]", "[isort]"):
                if re.search(rf"^\s*{re.escape(section)}\s*$", text, re.MULTILINE):
                    err(
                        name,
                        f"legacy {section} section present — Ruff never reads it; translate and delete",
                    )
    tool = pyproject.get("tool", {})
    for legacy in ("black", "isort"):
        if legacy in tool:
            err(
                "pyproject.toml",
                f"[tool.{legacy}] present alongside Ruff — silently ignored by Ruff and a conflict source; translate and delete",
            )

    # legacy tools still declared as dependencies
    dep_lists: list[tuple[str, list]] = []
    project = pyproject.get("project", {})
    dep_lists.append(("project.dependencies", project.get("dependencies", []) or []))
    for group, deps in (project.get("optional-dependencies", {}) or {}).items():
        dep_lists.append((f"project.optional-dependencies.{group}", deps or []))
    for group, deps in (pyproject.get("dependency-groups", {}) or {}).items():
        deps = [d for d in (deps or []) if isinstance(d, str)]  # skip include-group tables
        dep_lists.append((f"dependency-groups.{group}", deps))
    for where, deps in dep_lists:
        for dep in deps:
            base = re.split(r"[\s\[<>=!~;]", dep.strip(), maxsplit=1)[0].lower()
            if base in LEGACY_TOOLS or base.startswith("flake8-"):
                warn(
                    "pyproject.toml",
                    f"{where} still lists {base!r} — Ruff replaces it; remove unless using the documented hybrid pattern",
                )


def check_ruff_tables(root: Path, ruff: dict) -> None:
    where = "pyproject.toml"

    for key in DEPRECATED_TOP_LEVEL:
        if key in ruff:
            warn(
                where,
                f"[tool.ruff] {key!r} at top level is deprecated — move it under [tool.ruff.lint]",
            )

    lint = ruff.get("lint", {})
    select = [s for s in (lint.get("select") or ruff.get("select") or []) if isinstance(s, str)]
    extend_select = [s for s in (lint.get("extend-select") or []) if isinstance(s, str)]
    ignore = {s for s in (lint.get("ignore") or ruff.get("ignore") or []) if isinstance(s, str)}
    effective_select = select + extend_select

    if not effective_select:
        warn(
            where,
            "no [tool.ruff.lint] select — you are on Ruff's default rule set, which changed from E+F to 413 rules in 0.16 and moves on upgrades; write an explicit select",
        )
    if "ALL" in effective_select:
        warn(
            where,
            'select includes "ALL" — every Ruff upgrade silently enables new rules; prefer an explicit list (or hard-pin Ruff and review each bump)',
        )

    # This skill's default posture is lint + `ruff format` together, so
    # formatter-conflicting rules are always worth flagging.
    if effective_select:
        if selected("E501", effective_select) and "E501" not in ignore:
            warn(
                where,
                'E501 enabled while using ruff format — the formatter owns line length; add "E501" to [tool.ruff.lint] ignore',
            )
        for code in FORMATTER_CONFLICTS:
            if code not in ignore and selected(code, effective_select):
                warn(
                    where,
                    f"{code} conflicts with ruff format — remove its prefix from select or add it to ignore (docs.astral.sh/ruff/formatter/#conflicting-lint-rules)",
                )

    pfi = lint.get("per-file-ignores") or ruff.get("per-file-ignores") or {}
    for pattern in pfi:
        try:
            matched = any(root.glob(pattern)) or any(root.glob(f"**/{pattern}"))
        except (ValueError, NotImplementedError):
            continue
        if not matched:
            warn(
                where,
                f"per-file-ignores pattern {pattern!r} matches no files — typo? the ignore silently never applies",
            )


def check_target_version(pyproject: dict) -> None:
    ruff = pyproject.get("tool", {}).get("ruff", {})
    requires = pyproject.get("project", {}).get("requires-python")
    if not ruff.get("target-version") and not requires:
        warn(
            "pyproject.toml",
            "neither [tool.ruff] target-version nor project.requires-python is set — Ruff assumes py310 and UP autofixes may emit syntax your oldest runtime cannot parse",
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root", type=Path, default=Path.cwd(), help="repo root to check (default: cwd)"
    )
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    args = ap.parse_args()
    root = args.root.resolve()

    if not root.is_dir():
        print(f"ERROR usage: --root {root} is not a directory", file=sys.stderr)
        return 2
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.is_file():
        print(
            f"ERROR {pyproject_path}: not found — run from (or --root to) the package repo",
            file=sys.stderr,
        )
        return 2
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"ERROR pyproject.toml: cannot parse: {exc}", file=sys.stderr)
        return 2

    ruff_cfg = pyproject.get("tool", {}).get("ruff")
    ruff_toml = [n for n in ("ruff.toml", ".ruff.toml") if (root / n).is_file()]

    if ruff_cfg is None and not ruff_toml:
        err(
            "pyproject.toml",
            "no [tool.ruff] section (and no ruff.toml) — Ruff is not configured; see SKILL.md step 3",
        )
    if ruff_cfg is not None and ruff_toml:
        warn(
            "pyproject.toml",
            f"both [tool.ruff] and {ruff_toml[0]} exist — keep exactly one config source to avoid drift",
        )
    if ruff_toml and ruff_cfg is None:
        warn(
            ruff_toml[0],
            "config lives in ruff.toml — fine, but this checker only inspects pyproject.toml tables; legacy-remnant checks still apply",
        )

    if ruff_cfg is not None:
        check_ruff_tables(root, ruff_cfg)
        check_target_version(pyproject)
    if ruff_cfg is not None or ruff_toml:
        check_legacy_remnants(root, pyproject)

    n_err = n_warn = 0
    for level, where, msg in findings:
        print(f"{level} {where}: {msg}", file=sys.stderr)
        if level == "ERROR":
            n_err += 1
        else:
            n_warn += 1
    failed = n_err > 0 or (args.strict and n_warn > 0)
    print(f"{'FAIL' if failed else 'OK'}: {n_err} error(s), {n_warn} warning(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
