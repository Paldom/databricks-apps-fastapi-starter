#!/usr/bin/env python3
"""Check community health files for presence and minimum content.

Usage: check_health_files.py [--root DIR] [--remote owner/repo]
ERROR = required file missing; WARN = recommended missing or content probe failed;
INFO = optional. --remote adds GitHub's community-profile health percentage.
Exit 1 if any ERROR. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

LOCATIONS = ("", ".github/", "docs/")


def find(root: Path, *names: str) -> Path | None:
    for loc in LOCATIONS:
        for name in names:
            p = root / loc / name
            if p.is_file() and p.stat().st_size > 0:
                return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--remote", metavar="OWNER/REPO", default=None)
    args = ap.parse_args()
    root = args.root.resolve()
    errors = 0

    def report(level: str, msg: str) -> None:
        nonlocal errors
        if level == "ERROR":
            errors += 1
        print(f"{level}: {msg}")

    # Required at every project stage. LICENSE must be at the ROOT - GitHub's
    # detector (Licensee) does not reliably pick it up anywhere else.
    license_root = next((p for n in ("LICENSE", "LICENSE.md", "LICENSE.txt")
                         if (p := root / n).is_file() and p.stat().st_size > 0), None)
    if license_root:
        report("PASS", f"license: {license_root.relative_to(root)}")
    else:
        if find(root, "LICENSE", "LICENSE.md", "LICENSE.txt"):
            report("ERROR", "LICENSE exists but not at the repo root - move it there for GitHub detection")
        else:
            report("ERROR", "no LICENSE at the root - without one the repo is not open source")
    if find(root, "README.md", "README.rst", "README"):
        report("PASS", "README present")
    else:
        report("ERROR", "no README")

    # Recommended once contributors are expected.
    probes = {
        ("CONTRIBUTING.md",): (r"test|lint|setup|install|make |npm |pip |cargo ",
                               "CONTRIBUTING.md has no dev-setup/test commands - it must contain the repo's real commands"),
        ("CODE_OF_CONDUCT.md",): (r"enforce|contact|report",
                                  "CODE_OF_CONDUCT.md lacks an enforcement/contact section"),
        ("SECURITY.md",): (r"report|disclos|advisor|vulnerab",
                           "SECURITY.md does not describe how to report privately"),
        ("SUPPORT.md",): (r".", ""),
    }
    for names, (pattern, fail_msg) in probes.items():
        p = find(root, *names)
        if p is None:
            report("WARN", f"{names[0]} missing (recommended once outside contributors exist)")
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if pattern and not re.search(pattern, text, re.I):
            report("WARN", fail_msg or f"{names[0]} content probe failed")
        elif "[INSERT" in text or "{{" in text:
            report("WARN", f"{p.relative_to(root)} still contains an unfilled placeholder")
        else:
            report("PASS", f"{p.relative_to(root)} present")

    # CODEOWNERS: syntax sanity + the enforcement caveat.
    if p := find(root, "CODEOWNERS"):
        bad = [i for i, ln in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
               if ln.strip() and not ln.lstrip().startswith("#")
               and (len(ln.split()) < 2 or not all(o.startswith(("@", "docs@")) or "@" in o for o in ln.split()[1:]))]
        if bad:
            report("WARN", f"{p.relative_to(root)}: suspicious lines (need `path @owner`): {bad}")
        else:
            report("PASS", f"{p.relative_to(root)} present (inert unless a ruleset requires code-owner review)")
    else:
        report("INFO", "no CODEOWNERS - add one when specific paths need a named reviewer")

    if find(root, "GOVERNANCE.md"):
        report("PASS", "GOVERNANCE.md present")
    else:
        report("INFO", "GOVERNANCE.md absent (one page beats none once decisions involve several people)")
    # CITATION.cff and FUNDING.yml have strict locations: root, and .github/ only.
    if (root / "CITATION.cff").is_file():
        report("PASS", "CITATION.cff present at root")
    elif find(root, "CITATION.cff"):
        report("WARN", "CITATION.cff exists but not at the repo root - the Cite button needs it there")
    else:
        report("INFO", "CITATION.cff absent (research software only)")
    if (root / ".github/FUNDING.yml").is_file():
        report("PASS", ".github/FUNDING.yml present")
    elif (root / "FUNDING.yml").is_file() or (root / "docs/FUNDING.yml").is_file():
        report("WARN", "FUNDING.yml exists outside .github/ - GitHub only reads .github/FUNDING.yml repo-locally")
    else:
        report("INFO", ".github/FUNDING.yml absent (enables the Sponsor button)")

    if args.remote:
        try:
            proc = subprocess.run(["gh", "api", f"repos/{args.remote}/community/profile",
                                   "--jq", ".health_percentage"], capture_output=True, text=True)
            if proc.returncode == 0:
                report("INFO", f"GitHub community profile health: {proc.stdout.strip()}% "
                               "(public-repo metric; counts files this script checks plus templates)")
            else:
                report("INFO", f"community profile unavailable ({proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else 'unknown'})")
        except (OSError, FileNotFoundError):
            report("INFO", "gh CLI not found - skipped community-profile check")

    print(f"{'FAIL' if errors else 'OK'}: {errors} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
