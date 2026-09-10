#!/usr/bin/env python3
"""Static audit of GitHub Actions workflows for Node-CI hygiene.

Usage: check_workflows.py [--root DIR] [--require-merge-group]
ERROR (exit 1): third-party action not SHA-pinned, official action on a mutable
branch ref (@main/@master), EOL Node versions (incl. matrix lists), missing or
write-all top-level permissions, aggregator result-check that ignores
cancelled/skipped. WARN: missing merge_group (ERROR with --require-merge-group,
for repos using merge queues), missing timeout/concurrency. Line-based (stdlib
only) - it flags, humans/agents fix. EOL list is version-gated: update when
Node lines change status.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Verify against https://nodejs.org/en/about/previous-releases when editing.
# Odd majors are never LTS: each is EOL eight months after release (25 → 2026-06-01).
EOL_NODE = {"14", "15", "16", "17", "18", "19", "20", "21", "23", "25"}
OFFICIAL_PREFIXES = ("actions/", "github/")
USES_RE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)(\s*#.*)?$")
SHA_RE = re.compile(r"@[0-9a-f]{40}$")
MAJOR_TAG_RE = re.compile(r"@v\d+(\.\d+){0,2}$")
NODE_VER_RE = re.compile(r"node-version[^\n]*?[\"'\[]?(\d{2})")
# matrix lists like `node: [20, 22]` / `node-version: [ '20.x', 22 ]`
MATRIX_LIST_RE = re.compile(r"^\s*node(?:-version)?:\s*\[([^\]]*)\]", re.M)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument(
        "--require-merge-group",
        action="store_true",
        help="treat missing merge_group as an error (repos using merge queues)",
    )
    args = ap.parse_args()
    root = args.root.resolve()
    wf_dir = root / ".github" / "workflows"
    errors = 0

    def report(level: str, msg: str) -> None:
        nonlocal errors
        if level == "ERROR":
            errors += 1
        print(f"{level}: {msg}")

    files = (
        sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))) if wf_dir.is_dir() else []
    )
    if not files:
        report("ERROR", f"no workflows found under {wf_dir}")
        print("FAIL: 1 error(s)")
        return 1

    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = f.relative_to(root)
        if not re.search(r"^permissions:", text, re.M):
            report("ERROR", f"{rel}: no top-level permissions block (default token is too broad)")
        if re.search(r"permissions:\s*write-all", text):
            report("ERROR", f"{rel}: permissions: write-all - least privilege, always")
        for i, ln in enumerate(text.splitlines(), 1):
            m = USES_RE.match(ln)
            if not m:
                continue
            action = m.group(1)
            if action.startswith("./") or action.startswith("docker://"):
                continue
            name = action.split("@")[0]
            official = any(name.startswith(p) for p in OFFICIAL_PREFIXES)
            if not official and not SHA_RE.search(action):
                report("ERROR", f"{rel}:{i}: third-party action not SHA-pinned: {action}")
            elif official and not (SHA_RE.search(action) or MAJOR_TAG_RE.search(action)):
                report(
                    "ERROR",
                    f"{rel}:{i}: official action on a mutable ref: {action} "
                    "(use @vN or a full SHA, never @main)",
                )
        # EOL Node lines - both node-version keys and matrix lists.
        for m in NODE_VER_RE.finditer(text):
            if m.group(1) in EOL_NODE:
                report(
                    "ERROR",
                    f"{rel}: Node {m.group(1)} referenced - EOL line (verify against nodejs.org)",
                )
        for m in MATRIX_LIST_RE.finditer(text):
            for v in re.findall(r"\d{2}", m.group(1)):
                if v in EOL_NODE:
                    report("ERROR", f"{rel}: Node {v} in matrix list - EOL line")
        # `pull_request:` mapping form, `- pull_request` list item, or `on: [pull_request]`
        has_pr = re.search(
            r"(^\s*-?\s*pull_request\s*:?\s*(#.*)?$)|(^on:\s*\[[^\]]*\bpull_request\b)", text, re.M
        )
        if has_pr and "merge_group" not in text:
            report(
                "ERROR" if args.require_merge_group else "WARN",
                f"{rel}: pull_request without merge_group - merge queues will stall on this workflow",
            )
        if "timeout-minutes" not in text:
            report("WARN", f"{rel}: no timeout-minutes on any job")
        if "concurrency" not in text:
            report("WARN", f"{rel}: no concurrency group (superseded runs will pile up)")

    all_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in files)
    if "strategy:" in all_text and "if: always()" not in all_text:
        report(
            "WARN",
            "matrix jobs found but no always()-guarded aggregator job - "
            "required checks on individual legs are brittle",
        )
    # Aggregator must fail closed, judged per file (a result test in another
    # workflow proves nothing about this one). `if: always()` with no
    # needs.*.result test at all is the worst case: it is green whatever failed.
    # A test that names only 'failure' passes on cancelled/skipped legs. Accept
    # the != 'success' pattern (covers all) or explicit cancelled+skipped.
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        if "if: always()" not in text:
            continue
        rel = f.relative_to(root)
        checks = re.findall(r"needs[^\n]*result[^\n]*", text)
        joined = " ".join(checks)
        fail_closed = (
            "!= 'success'" in joined
            or '!= "success"' in joined
            or ("cancelled" in joined and "skipped" in joined)
        )
        if not checks:
            report(
                "ERROR",
                f"{rel}: a job runs with if: always() but nothing tests needs.*.result - "
                "the aggregator is green even when every dependency failed",
            )
        elif not fail_closed:
            report(
                "ERROR",
                f"{rel}: aggregator result-check does not fail closed - test "
                "result != 'success' (covers failure, cancelled, and skipped)",
            )

    print(f"{'FAIL' if errors else 'OK'}: {errors} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
