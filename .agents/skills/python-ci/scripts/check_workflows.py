#!/usr/bin/env python3
"""Read-only hygiene checks for GitHub Actions workflow files.

Scans .github/workflows/*.yml|*.yaml and prints one finding per line:

    ERROR <file>:<line>: [E00x] <message>
    WARN  <file>:<line>: [W00x] <message>

Never modifies anything. Exit codes: 0 = no errors (warnings allowed),
1 = errors found (or warnings with --strict), 2 = usage problem (no
workflow files found).

Checks
  E001  `uses:` ref is not a 40-hex commit SHA (mutable tag/branch — repointable)
  E002  unquoted python-version ending in 0 (YAML parses 3.10 as the float 3.1)
  E003  aggregator-style job (all-checks-passed/…) without `if: always()` —
        it gets skipped when a dependency fails, and skipped counts as success
  W001  file sets no `permissions:` at workflow or job level (inherits repo default)
  W002  `pull_request_target` trigger present (secrets + untrusted fork input)
  W003  no `merge_group` trigger (only with --require-merge-group)
  W004  unquoted numeric python-version (works today, fragile — quote it)

Usage:
    python3 scripts/check_workflows.py [--repo PATH] [--require-merge-group] [--strict]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
USES_RE = re.compile(r"^\s*(?:-\s+)?uses:\s*(['\"]?)([^'\"#\s]+)\1\s*(?:#.*)?$")
JOB_KEY_RE = re.compile(r"^(\s+)([A-Za-z_][A-Za-z0-9_-]*):\s*(?:#.*)?$")
AGGREGATOR_NAME_RE = re.compile(
    r"(all[-_]?checks|checks[-_]?passed|all[-_]?green|aggregate|ci[-_]?gate|status[-_]?check)",
    re.IGNORECASE,
)
ALWAYS_RE = re.compile(r"^\s*if:\s*.*always\(\)")
PV_INLINE_RE = re.compile(r"^\s*(?:-\s+)?python-version:\s*(\S.*?)\s*(?:#.*)?$")
BARE_VERSION_RE = re.compile(r"^\d+\.\d+$")
LIST_ITEM_RE = re.compile(r"^(\s*)-\s*(.+?)\s*(?:#.*)?$")

findings: list[tuple[str, Path, int, str, str]] = []


def add(level: str, path: Path, line: int, code: str, msg: str) -> None:
    findings.append((level, path, line, code, msg))


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def check_uses(path: Path, lineno: int, line: str) -> None:
    m = USES_RE.match(line)
    if not m:
        return
    ref = m.group(2)
    if ref.startswith("./"):
        return  # same-repo action/workflow: no ref to pin
    if ref.startswith("docker://"):
        if "@sha256:" not in ref:
            add(
                "ERROR",
                path,
                lineno,
                "E001",
                f"docker action {ref!r} is not pinned by digest (@sha256:...)",
            )
        return
    if "@" not in ref:
        add(
            "ERROR",
            path,
            lineno,
            "E001",
            f"action {ref!r} has no ref at all — pin to a full commit SHA",
        )
        return
    pin = ref.rsplit("@", 1)[1]
    if not SHA_RE.match(pin):
        add(
            "ERROR",
            path,
            lineno,
            "E001",
            f"action {ref!r} pinned to mutable ref {pin!r} — use the full 40-char "
            "commit SHA with a trailing `# vX.Y.Z` comment",
        )


def check_python_versions(path: Path, lines: list[str]) -> None:
    def flag(token: str, lineno: int) -> None:
        token = token.strip()
        if token.startswith(("'", '"')):
            return
        if BARE_VERSION_RE.match(token):
            if token.split(".")[1].endswith("0"):
                add(
                    "ERROR",
                    path,
                    lineno,
                    "E002",
                    f"unquoted python-version {token} is YAML for the float "
                    f"{float(token)} — quote it: '{token}'",
                )
            else:
                add(
                    "WARN",
                    path,
                    lineno,
                    "W004",
                    f"unquoted numeric python-version {token} — quote it; "
                    "trailing-zero versions (3.10) silently break",
                )

    i = 0
    while i < len(lines):
        line = lines[i]
        m = PV_INLINE_RE.match(line)
        i += 1
        if not m:
            continue
        value = m.group(1)
        if value.startswith("["):
            for token in value.strip("[]").split(","):
                flag(token, i)
        elif value:  # scalar form: python-version: 3.10
            flag(value, i)
        else:
            continue
        if value:
            continue
    # block-list form: python-version:\n  - 3.10
    for idx, line in enumerate(lines):
        if re.match(r"^\s*python-version:\s*(?:#.*)?$", line):
            base_indent = indent_of(line)
            j = idx + 1
            while j < len(lines):
                item = LIST_ITEM_RE.match(lines[j])
                if not item or indent_of(lines[j]) <= base_indent:
                    break
                flag(item.group(2), j + 1)
                j += 1


def job_blocks(lines: list[str]) -> list[tuple[str, int, list[str]]]:
    """Return (job_name, start_lineno, block_lines) for each job under `jobs:`."""
    blocks: list[tuple[str, int, list[str]]] = []
    try:
        jobs_at = next(i for i, ln in enumerate(lines) if re.match(r"^jobs:\s*(#.*)?$", ln))
    except StopIteration:
        return blocks
    job_indent = None
    current: tuple[str, int, list[str]] | None = None
    for i in range(jobs_at + 1, len(lines)):
        ln = lines[i]
        if not ln.strip() or ln.lstrip().startswith("#"):
            if current:
                current[2].append(ln)
            continue
        ind = indent_of(ln)
        if ind == 0:  # left the jobs: mapping
            break
        m = JOB_KEY_RE.match(ln)
        if m and (job_indent is None or ind == job_indent):
            job_indent = ind
            if current:
                blocks.append(current)
            current = (m.group(2), i + 1, [])
        elif current:
            current[2].append(ln)
    if current:
        blocks.append(current)
    return blocks


def check_file(path: Path, require_merge_group: bool) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        add("ERROR", path, 1, "E000", f"cannot read file: {exc}")
        return
    lines = text.splitlines()
    code_lines = [(n, ln) for n, ln in enumerate(lines, 1) if not ln.lstrip().startswith("#")]

    for n, ln in code_lines:
        check_uses(path, n, ln)
        if re.search(r"^\s*(-\s+)?pull_request_target\s*:?\s*(#.*)?$", ln):
            add(
                "WARN",
                path,
                n,
                "W002",
                "pull_request_target trigger — runs with base-repo secrets on "
                "untrusted fork input; audit or replace with pull_request",
            )

    check_python_versions(path, lines)

    if not any(re.match(r"^\s*permissions\s*:", ln) for _, ln in code_lines):
        add(
            "WARN",
            path,
            1,
            "W001",
            "no `permissions:` block — GITHUB_TOKEN inherits the repo default "
            "(often broad write); set `permissions: contents: read` at workflow level",
        )

    if require_merge_group and not any(
        re.search(r"^\s*(-\s+)?merge_group\s*:?\s*(#.*)?$", ln) for _, ln in code_lines
    ):
        add(
            "WARN",
            path,
            1,
            "W003",
            "no merge_group trigger — with a merge queue enabled, required checks "
            "from this workflow never report at queue time",
        )

    for name, lineno, block in job_blocks(lines):
        if AGGREGATOR_NAME_RE.search(name):
            has_needs = any(re.match(r"^\s*needs\s*:", ln) for ln in block)
            has_always = any(ALWAYS_RE.match(ln) for ln in block)
            if has_needs and not has_always:
                add(
                    "ERROR",
                    path,
                    lineno,
                    "E003",
                    f"aggregator job {name!r} has needs: but no `if: always()` — "
                    "it will be SKIPPED when a dependency fails, and a skipped "
                    "required check counts as success",
                )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="repo root containing .github/workflows/ (default: cwd)",
    )
    ap.add_argument(
        "--require-merge-group",
        action="store_true",
        help="warn when a workflow lacks a merge_group trigger",
    )
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args()

    wf_dir = args.repo / ".github" / "workflows"
    files = sorted(p for p in wf_dir.glob("*.y*ml") if p.is_file()) if wf_dir.is_dir() else []
    if not files:
        print(f"ERROR {wf_dir}: no workflow files found", file=sys.stderr)
        return 2

    for f in files:
        check_file(f, args.require_merge_group)

    for level, path, line, code, msg in findings:
        stream = sys.stderr if level == "ERROR" else sys.stdout
        print(f"{level:<5} {path}:{line}: [{code}] {msg}", file=stream)

    n_err = sum(1 for f in findings if f[0] == "ERROR")
    n_warn = len(findings) - n_err
    failed = n_err + (n_warn if args.strict else 0)
    print(
        f"{'FAIL' if failed else 'OK'}: {n_err} error(s), {n_warn} warning(s) "
        f"across {len(files)} workflow file(s)"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
