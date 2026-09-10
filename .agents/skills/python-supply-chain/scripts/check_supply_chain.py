#!/usr/bin/env python3
"""Read-only supply-chain posture audit for a Python repository.

Checks for the presence and basic shape of supply-chain controls: Dependabot
config, lockfile, CODEOWNERS coverage, scanning workflows, security policy and
(with --github) GitHub-side settings via the `gh` CLI. Never modifies anything.

Usage:
    python3 check_supply_chain.py --root /path/to/repo
    python3 check_supply_chain.py --root . --github     # also query repo settings
    python3 check_supply_chain.py --root . --strict     # WARN counts as FAIL

Output: one `LEVEL check-id: detail` line per check, where LEVEL is
PASS | WARN | FAIL | NOTE, then a RESULT summary line.
Exit codes: 0 = no FAILs (WARNs allowed unless --strict), 1 = FAILs present,
2 = usage/environment error (bad root, gh missing with --github).

Python 3.10+, stdlib only. YAML/TOML are matched with conservative regexes on
purpose: no third-party parser, and a miss degrades to WARN, never a crash.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

results: list[tuple[str, str, str]] = []  # (level, check, detail)


def report(level: str, check: str, detail: str) -> None:
    results.append((level, check, detail))


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def workflow_texts(root: Path) -> dict[str, str]:
    wf_dir = root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return {}
    return {
        p.name: read(p)
        for p in sorted(wf_dir.iterdir())
        if p.suffix in (".yml", ".yaml") and p.is_file()
    }


def check_dependabot(root: Path) -> None:
    cfg = None
    for name in ("dependabot.yml", "dependabot.yaml"):
        candidate = root / ".github" / name
        if candidate.is_file():
            cfg = candidate
            break
    if cfg is None:
        report(
            "FAIL",
            "dependabot-config",
            ".github/dependabot.yml not found — no dependency-update automation",
        )
        return
    text = read(cfg)
    ecosystems = re.findall(r"package-ecosystem:\s*[\"']?([A-Za-z-]+)", text)
    if any(e in ("pip", "uv") for e in ecosystems):
        report(
            "PASS",
            "dependabot-python",
            f"{cfg.name} covers a Python ecosystem ({', '.join(sorted(set(ecosystems)))})",
        )
    else:
        report(
            "FAIL",
            "dependabot-python",
            f"{cfg.name} has no pip/uv entry (found: {sorted(set(ecosystems)) or 'none'})",
        )
    if "github-actions" in ecosystems:
        report("PASS", "dependabot-actions", "github-actions ecosystem entry present")
    else:
        report(
            "WARN",
            "dependabot-actions",
            "no github-actions entry — action versions won't get update PRs",
        )
    if re.search(r"^\s*cooldown\s*:", text, re.MULTILINE):
        report("PASS", "dependabot-cooldown", "cooldown configured")
    else:
        report(
            "WARN",
            "dependabot-cooldown",
            "no cooldown — freshly published (possibly malicious) versions are adopted immediately",
        )
    if re.search(r"^\s*groups\s*:", text, re.MULTILINE):
        report("PASS", "dependabot-groups", "update grouping configured")
    else:
        report(
            "WARN",
            "dependabot-groups",
            "no groups — expect one PR per dependency (noise breeds auto-merge)",
        )


def check_lockfile(root: Path) -> None:
    for name in ("uv.lock", "poetry.lock", "pdm.lock", "Pipfile.lock"):
        if (root / name).is_file():
            report("PASS", "lockfile", f"{name} present")
            return
    reqs = sorted(root.glob("requirements*.txt")) + sorted(root.glob("requirements/*.txt"))
    if reqs:
        if any("--hash=" in read(r) for r in reqs):
            report("PASS", "lockfile", f"hash-pinned requirements ({reqs[0].name}, ...)")
        else:
            report(
                "WARN",
                "lockfile",
                "requirements files found but without --hash pins — "
                "substitution attacks are invisible",
            )
        return
    report(
        "FAIL",
        "lockfile",
        "no lockfile (uv.lock/poetry.lock/pdm.lock/requirements) — "
        "the dependency set is unpinned; fix via packaging setup first",
    )


def check_codeowners(root: Path) -> None:
    for rel in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"):
        path = root / rel
        if path.is_file():
            text = read(path)
            rules = [
                ln.split()[0]
                for ln in text.splitlines()
                if ln.strip() and not ln.lstrip().startswith("#") and ln.split()
            ]
            if any(r.startswith((".github", "/.github")) for r in rules):
                report("PASS", "codeowners", f"{rel} present and covers .github/")
            else:
                report(
                    "WARN",
                    "codeowners",
                    f"{rel} present but no rule for /.github/ — whoever edits "
                    "workflows or dependabot.yml bypasses every other control",
                )
            star_rules = [i for i, r in enumerate(rules) if r == "*"]
            if star_rules and star_rules[-1] == len(rules) - 1 and len(rules) > 1:
                report(
                    "WARN",
                    "codeowners-order",
                    "catch-all '*' is the LAST rule — CODEOWNERS is "
                    "last-match-wins, so it overrides every specific rule above",
                )
            return
    report(
        "WARN",
        "codeowners",
        "no CODEOWNERS file — no mandatory review for automation-defining paths",
    )


def check_workflows(root: Path) -> None:
    flows = workflow_texts(root)
    joined = "\n".join(flows.values())
    if "codeql-action" in joined:
        report("PASS", "codeql", "CodeQL workflow present")
    else:
        report(
            "WARN",
            "codeql",
            "no CodeQL workflow — OK only if code scanning 'default setup' is "
            "enabled in repo settings (verify with --github)",
        )
    if re.search(r"gitleaks|trufflehog", joined, re.IGNORECASE):
        report("PASS", "secret-scan-ci", "CI secret-scan backstop present")
    else:
        report(
            "WARN",
            "secret-scan-ci",
            "no gitleaks/trufflehog workflow — GitHub push protection alone "
            "covers only high-confidence patterns",
        )
    if "scorecard-action" in joined:
        report("PASS", "scorecard", "OpenSSF Scorecard workflow present")
    else:
        report("NOTE", "scorecard", "no Scorecard workflow (optional posture dashboard)")
    if re.search(r"attest-build-provenance|attest-sbom|cyclonedx|anchore/sbom-action", joined):
        report("PASS", "sbom-provenance", "SBOM/attestation step found in workflows")
    else:
        report(
            "NOTE",
            "sbom-provenance",
            "no SBOM/attestation step in workflows (optional; relevant at release)",
        )
    unpinned = []
    for name, text in flows.items():
        for m in re.finditer(r"^\s*(?:-\s*)?uses:\s*([\w./-]+)@([\w.-]+)", text, re.MULTILINE):
            action, ref = m.group(1), m.group(2)
            if action.startswith("./"):
                continue
            if not re.fullmatch(r"[0-9a-f]{40}", ref):
                unpinned.append(f"{name}:{action}@{ref}")
    if unpinned:
        report(
            "NOTE",
            "action-pinning",
            f"{len(unpinned)} action ref(s) not pinned to a 40-char SHA "
            f"(e.g. {unpinned[0]}) — pinning policy is python-ci territory",
        )


def check_misc(root: Path) -> None:
    if any(
        (root / p).is_file() for p in ("SECURITY.md", ".github/SECURITY.md", "docs/SECURITY.md")
    ):
        report("PASS", "security-policy", "SECURITY.md present")
    else:
        report(
            "WARN",
            "security-policy",
            "no SECURITY.md — no documented way to report a vulnerability",
        )
    pyproject = root / "pyproject.toml"
    if pyproject.is_file() and re.search(r"^\s*exclude-newer\s*=", read(pyproject), re.MULTILINE):
        report("PASS", "freshness-window", "[tool.uv] exclude-newer configured")
    else:
        report(
            "NOTE",
            "freshness-window",
            "no [tool.uv] exclude-newer — resolver has no freshness buffer "
            "against just-published packages (optional, uv projects)",
        )


def gh_json(args: list[str], cwd: Path | None = None) -> tuple[int, dict | list | None]:
    try:
        proc = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=30, cwd=str(cwd) if cwd else None
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, {"error": str(exc)}
    if proc.returncode != 0:
        return proc.returncode, None
    try:
        return 0, json.loads(proc.stdout) if proc.stdout.strip() else {}
    except ValueError:
        return 0, {}


def check_github(root: Path) -> None:
    if shutil.which("gh") is None:
        print(
            "ERROR github-checks: gh CLI not found on PATH (needed for --github)", file=sys.stderr
        )
        raise SystemExit(2)
    rc, view = gh_json(
        ["repo", "view", "--json", "nameWithOwner"], cwd=root
    )  # the audited root, not the shell cwd
    if rc != 0 or not isinstance(view, dict) or "nameWithOwner" not in view:
        report(
            "WARN",
            "github-repo",
            "could not resolve the GitHub repo via `gh repo view` "
            "(not a GitHub remote, or gh unauthenticated) — skipping API checks",
        )
        return
    repo = view["nameWithOwner"]
    rc, data = gh_json(["api", f"repos/{repo}"])
    sec = (data or {}).get("security_and_analysis") or {} if isinstance(data, dict) else {}
    for key, check in (
        ("secret_scanning", "gh-secret-scanning"),
        ("secret_scanning_push_protection", "gh-push-protection"),
    ):
        status = (sec.get(key) or {}).get("status")
        if status == "enabled":
            report("PASS", check, f"{key} enabled")
        elif status == "disabled":
            report("FAIL", check, f"{key} disabled — enable it (free on public repos)")
        else:
            report("WARN", check, f"{key} state unknown (insufficient token scope or licensing)")
    rc, _ = gh_json(["api", f"repos/{repo}/vulnerability-alerts"])
    if rc == 0:
        report("PASS", "gh-dependabot-alerts", "Dependabot alerts enabled")
    else:
        report(
            "FAIL",
            "gh-dependabot-alerts",
            "Dependabot alerts disabled or not visible — enable with "
            f"`gh api -X PUT repos/{repo}/vulnerability-alerts`",
        )
    rc, setup = gh_json(["api", f"repos/{repo}/code-scanning/default-setup"])
    if rc == 0 and isinstance(setup, dict) and setup.get("state") == "configured":
        report("PASS", "gh-codeql-default", "code scanning default setup configured")
    elif rc == 0:
        report(
            "WARN",
            "gh-codeql-default",
            "code scanning default setup not configured (fine if an advanced "
            "CodeQL workflow exists)",
        )
    else:
        report(
            "WARN",
            "gh-codeql-default",
            "could not query code-scanning setup (licensing/permissions)",
        )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--root", type=Path, default=Path.cwd(), help="repository root to audit (default: cwd)"
    )
    ap.add_argument(
        "--github", action="store_true", help="also query GitHub-side settings via the gh CLI"
    )
    ap.add_argument("--strict", action="store_true", help="treat WARN as FAIL for the exit code")
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        print(f"ERROR root: {root} is not a directory", file=sys.stderr)
        return 2

    check_dependabot(root)
    check_lockfile(root)
    check_codeowners(root)
    check_workflows(root)
    check_misc(root)
    if args.github:
        check_github(root)

    order = {"FAIL": 0, "WARN": 1, "NOTE": 2, "PASS": 3}
    for level, check, detail in sorted(results, key=lambda r: order[r[0]]):
        print(f"{level} {check}: {detail}")
    counts = {lvl: sum(1 for r in results if r[0] == lvl) for lvl in order}
    failing = counts["FAIL"] + (counts["WARN"] if args.strict else 0)
    print(
        f"RESULT: {counts['FAIL']} fail, {counts['WARN']} warn, "
        f"{counts['NOTE']} note, {counts['PASS']} pass"
    )
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
