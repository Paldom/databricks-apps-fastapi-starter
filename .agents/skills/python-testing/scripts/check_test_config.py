#!/usr/bin/env python3
"""Read-only audit of pytest/coverage configuration in a Python package repo.

Finds the misconfigurations that make test infrastructure lie: shadowed or
split config sources, a config table the installed tools silently ignore,
missing branch coverage, and coverage gates that were never wired up.

This script only READS files. It never modifies the repo, never runs the test
suite, and never installs anything. Version checks that require executing tools
(e.g. `pytest --version`) are intentionally left to the caller.

Usage:
    python3 check_test_config.py [--root PATH] [--strict]

Output: one machine-readable line per finding:
    ERROR <file>: <message>
    WARN  <file>: <message>
    INFO  <file>: <message>

Exit codes: 0 = no errors (warnings allowed unless --strict), 1 = errors found.

Requires Python 3.11+ for full TOML-aware checks (stdlib tomllib); on 3.10 it
falls back to section-presence checks only and says so.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10: degrade to text-level checks
    tomllib = None

errors: list[str] = []
warnings: list[str] = []
infos: list[str] = []


def err(where: str, msg: str) -> None:
    errors.append(f"ERROR {where}: {msg}")


def warn(where: str, msg: str) -> None:
    warnings.append(f"WARN  {where}: {msg}")


def info(where: str, msg: str) -> None:
    infos.append(f"INFO  {where}: {msg}")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        err(str(path), f"cannot read: {exc}")
        return ""


def has_section(text: str, section: str) -> bool:
    """Text-level TOML/INI section presence check, e.g. section='tool.pytest'."""
    pattern = re.compile(r"^\s*\[" + re.escape(section) + r"(\.[A-Za-z0-9_.-]+)?\]", re.M)
    return bool(pattern.search(text))


def has_exact_section(text: str, section: str) -> bool:
    pattern = re.compile(r"^\s*\[" + re.escape(section) + r"\]", re.M)
    return bool(pattern.search(text))


def addopts_as_string(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root", type=Path, default=Path.cwd(), help="package repo root (default: cwd)"
    )
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        err(str(root), "not a directory")
        print(errors[0], file=sys.stderr)
        print("FAIL: 1 error(s), 0 warning(s)")
        return 1

    pyproject = root / "pyproject.toml"
    pytest_ini = root / "pytest.ini"
    # pytest >= 9: pytest.toml / .pytest.toml outrank everything, even when empty;
    # .pytest.ini is the hidden twin of pytest.ini.
    toml_configs = [
        p
        for p in (root / "pytest.toml", root / ".pytest.toml", root / ".pytest.ini")
        if p.is_file()
    ]
    setup_cfg = root / "setup.cfg"
    tox_ini = root / "tox.ini"
    coveragerc = root / ".coveragerc"

    pp_text = read_text(pyproject) if pyproject.is_file() else ""
    pp_data: dict = {}
    if pp_text and tomllib is not None:
        try:
            pp_data = tomllib.loads(pp_text)
        except tomllib.TOMLDecodeError as exc:
            err(str(pyproject), f"invalid TOML: {exc}")
    elif pp_text and tomllib is None:
        info(
            str(pyproject),
            "Python < 3.11 (no tomllib) — key-level checks skipped, section-presence checks only",
        )

    tool = pp_data.get("tool", {}) if isinstance(pp_data.get("tool", {}), dict) else {}
    pp_pytest_tbl = tool.get("pytest")
    if tomllib is not None and pp_text:
        pp_has_ini_options = isinstance(pp_pytest_tbl, dict) and "ini_options" in pp_pytest_tbl
        pp_has_native_pytest = isinstance(pp_pytest_tbl, dict) and any(
            k != "ini_options" for k in pp_pytest_tbl
        )
        pp_has_coverage = "coverage" in tool
    else:
        pp_has_ini_options = has_exact_section(pp_text, "tool.pytest.ini_options")
        pp_has_native_pytest = has_exact_section(pp_text, "tool.pytest")
        pp_has_coverage = has_section(pp_text, "tool.coverage")

    pp_has_pytest = pp_has_ini_options or pp_has_native_pytest

    # --- pytest config source conflicts (pytest reads the FIRST match only) ---
    setup_cfg_text = read_text(setup_cfg) if setup_cfg.is_file() else ""
    tox_ini_text = read_text(tox_ini) if tox_ini.is_file() else ""
    setup_cfg_has_pytest = bool(setup_cfg_text) and has_exact_section(setup_cfg_text, "tool:pytest")
    tox_ini_has_pytest = bool(tox_ini_text) and has_exact_section(tox_ini_text, "pytest")

    if pytest_ini.is_file() and pp_has_pytest:
        err(
            str(pytest_ini),
            "pytest.ini exists alongside pytest config in pyproject.toml — pytest.ini silently wins; merge into one source and delete the other",
        )
    for cfg in toml_configs:
        if pp_has_pytest or pytest_ini.is_file():
            err(
                str(cfg),
                f"{cfg.name} exists alongside other pytest config — it takes precedence over every other file, even when empty; keep exactly one source",
            )
    if setup_cfg_has_pytest and pp_has_pytest:
        warn(
            str(setup_cfg),
            "[tool:pytest] in setup.cfg alongside pytest config in pyproject.toml — only one source is read; merge and delete the loser",
        )
    if tox_ini_has_pytest and pp_has_pytest:
        warn(
            str(tox_ini),
            "[pytest] section in tox.ini alongside pytest config in pyproject.toml — only one source is read; merge and delete the loser",
        )

    # --- the two pyproject tables ---
    if pp_has_native_pytest and pp_has_ini_options:
        err(
            str(pyproject),
            "both [tool.pytest] and [tool.pytest.ini_options] present — pytest reads one table; merge into the one your pytest major supports",
        )
    elif pp_has_native_pytest:
        info(
            str(pyproject),
            "[tool.pytest] native table (pytest >= 9.0) — SILENTLY ignored on older pytest; confirm with `pytest --version`, or use [tool.pytest.ini_options] if < 9 must work",
        )

    if not (
        pp_has_pytest
        or pytest_ini.is_file()
        or toml_configs
        or setup_cfg_has_pytest
        or tox_ini_has_pytest
    ):
        warn(
            str(root),
            "no pytest configuration found in pyproject.toml, pytest.toml, pytest.ini, setup.cfg, or tox.ini — add [tool.pytest.ini_options] (or [tool.pytest] on pytest >= 9) with testpaths and strict flags",
        )

    # --- coverage config source conflicts (.coveragerc wins) ---
    if coveragerc.is_file() and pp_has_coverage:
        err(
            str(coveragerc),
            ".coveragerc exists alongside [tool.coverage.*] in pyproject.toml — .coveragerc silently wins; keep exactly one source",
        )

    # --- key-level coverage checks (TOML-aware only) ---
    if tomllib is not None and pp_has_coverage and isinstance(tool.get("coverage"), dict):
        cov = tool["coverage"]
        run = cov.get("run", {}) if isinstance(cov.get("run", {}), dict) else {}
        report = cov.get("report", {}) if isinstance(cov.get("report", {}), dict) else {}

        if run.get("branch") is not True:
            warn(
                str(pyproject),
                "[tool.coverage.run] branch is not true — line-only coverage overstates; set branch = true",
            )
        if run.get("parallel") is True and run.get("relative_files") is not True:
            warn(
                str(pyproject),
                "[tool.coverage.run] parallel = true without relative_files = true — combining data across paths/runners will mismatch files",
            )

        ini = pp_pytest_tbl.get("ini_options", {}) if isinstance(pp_pytest_tbl, dict) else {}
        addopts = addopts_as_string(ini.get("addopts", "")) if isinstance(ini, dict) else ""
        has_gate = "fail_under" in report or "--cov-fail-under" in addopts
        if not has_gate:
            warn(
                str(pyproject),
                "no coverage gate found — set fail_under under [tool.coverage.report] (80-90), then prove it trips with a non-zero exit",
            )
        if "--cov" in addopts.split() or "--cov=" in addopts:
            info(
                str(pyproject),
                "--cov baked into pytest addopts — every run (incl. single-test debugging) pays coverage overhead; --no-cov disables per run",
            )

    for line in errors + warnings + infos:
        print(line, file=sys.stderr)
    n_fail = len(errors) + (len(warnings) if args.strict else 0)
    print(
        f"{'FAIL' if n_fail else 'OK'}: {len(errors)} error(s), {len(warnings)} warning(s), {len(infos)} info"
    )
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
