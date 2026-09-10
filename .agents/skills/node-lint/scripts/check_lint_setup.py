#!/usr/bin/env python3
"""Sanity-check a repo's lint/format setup for the failure modes that ship broken.

Usage: check_lint_setup.py [--root DIR]
ERROR (exit 1): legacy .eslintrc* coexisting with flat config or any config at
all under ESLint v10+, two formatters configured, no lint tool at all.
WARN: scripts not wired, formatter conflicts likely. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

LEGACY = (
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".eslintrc.json",
    ".eslintrc.yml",
    ".eslintrc.yaml",
)
FLAT = (
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.cjs",
    "eslint.config.ts",
    "eslint.config.mts",
    "eslint.config.cts",
)
BIOME = ("biome.json", "biome.jsonc")
PRETTIER = (
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.json5",
    ".prettierrc.yml",
    ".prettierrc.yaml",
    ".prettierrc.toml",
    ".prettierrc.js",
    ".prettierrc.cjs",
    ".prettierrc.mjs",
    "prettier.config.js",
    "prettier.config.cjs",
    "prettier.config.mjs",
)


def strip_jsonc(text: str) -> str:
    """Drop // and /* */ comments and trailing commas, but never inside strings.

    A regex that deletes `//...` corrupts every `"$schema": "https://..."` line;
    this walks the text once and tracks whether it is inside a JSON string.
    """
    out: list[str] = []
    i, n, in_str = 0, len(text), False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
            out.append(ch)
        elif text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                break
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        else:
            out.append(ch)
        i += 1
    return re.sub(r",\s*([}\]])", r"\1", "".join(out))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."))
    root = ap.parse_args().root.resolve()
    errors = 0

    def report(level: str, msg: str) -> None:
        nonlocal errors
        if level == "ERROR":
            errors += 1
        print(f"{level}: {msg}")

    legacy = [n for n in LEGACY if (root / n).exists()]
    flat = [n for n in FLAT if (root / n).exists()]
    biome = [n for n in BIOME if (root / n).exists()]
    prettier = [n for n in PRETTIER if (root / n).exists()]

    pkg = {}
    pkg_path = root / "package.json"
    if pkg_path.is_file():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report("ERROR", "package.json is not valid JSON")
    if "prettier" in pkg:
        prettier.append("package.json#prettier")

    if legacy and flat:
        report(
            "ERROR",
            f"legacy eslintrc ({', '.join(legacy)}) coexists with flat config "
            f"({', '.join(flat)}) - modern ESLint loads only flat; delete the legacy files",
        )
    elif legacy:
        report(
            "ERROR",
            f"only legacy eslintrc found ({', '.join(legacy)}) - ESLint v10+ does not load it; "
            "migrate to flat config",
        )
    if biome and (flat or legacy):
        report(
            "WARN",
            "both Biome and ESLint configured - deliberate split setups are fine, "
            "accidental overlap is not; confirm each tool's scope is disjoint",
        )
    biome_formats = False
    if biome:
        raw = (root / biome[0]).read_text(encoding="utf-8", errors="replace")
        try:
            conf = json.loads(strip_jsonc(raw))
            biome_formats = (conf.get("formatter") or {}).get("enabled", True)
        except (json.JSONDecodeError, OSError):
            # Fail closed: if we cannot parse it, assume the formatter is on.
            biome_formats = True
            report("WARN", f"{biome[0]} could not be parsed - assuming its formatter is enabled")
    if biome_formats and prettier:
        report(
            "ERROR",
            f"two formatters configured (Biome formatter + {', '.join(prettier)}) - pick one",
        )

    if not (biome or flat or legacy):
        report("ERROR", "no lint tool configured (no biome.json, no eslint config)")

    scripts = pkg.get("scripts", {}) if isinstance(pkg, dict) else {}
    joined = " ".join(str(v) for v in scripts.values())
    if (biome or flat) and "lint" not in scripts:
        report("WARN", "no `lint` script in package.json - CI and contributors need one command")
    if flat and prettier and "format" not in scripts:
        report("WARN", "Prettier configured but no `format` script wired")
    if flat and "--max-warnings" not in joined:
        report("WARN", "ESLint scripts do not use --max-warnings=0 - warnings will rot")

    for name, ok in (
        ("biome", bool(biome)),
        ("eslint flat", bool(flat)),
        ("prettier", bool(prettier)),
    ):
        if ok:
            print(f"INFO: {name} config present")
    print(f"{'FAIL' if errors else 'OK'}: {errors} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
