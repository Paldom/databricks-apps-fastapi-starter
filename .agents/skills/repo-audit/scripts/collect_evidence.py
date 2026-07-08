#!/usr/bin/env python3
"""Collect mechanical evidence for a repo audit; JSON to stdout.

Usage: collect_evidence.py [owner/repo]
With no argument, audits the repo for the cwd (file checks read the local working
tree, resolved to the git toplevel). With owner/repo, file checks go through the
GitHub contents API. Every value is tri-state: true/false/counts when confirmed,
null when NOT DETERMINABLE (403, missing scopes, plan limits) - report null as
"unknown", never as failing. The `not_collected` list names checks that are
manual/agent-judged by design; a report must never mark them complete from this
evidence. Exit 1 only if the repo itself cannot be read. Needs `gh`. Stdlib only.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
from pathlib import Path

VIEW_FIELDS = ("name,nameWithOwner,description,repositoryTopics,homepageUrl,isPrivate,"
               "openGraphImageUrl,defaultBranchRef,licenseInfo,latestRelease,pushedAt,"
               "stargazerCount,forkCount,hasIssuesEnabled,hasDiscussionsEnabled,isArchived")
HEALTH_FILES = ["README.md", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
                "SECURITY.md", "SUPPORT.md", "GOVERNANCE.md", "CITATION.cff",
                ".github/FUNDING.yml", ".github/dependabot.yml"]
MULTI_LOCATION = {  # checked at every listed path; recorded under the dict key
    "CODEOWNERS": [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"],
    "PULL_REQUEST_TEMPLATE": [".github/PULL_REQUEST_TEMPLATE.md", "PULL_REQUEST_TEMPLATE.md",
                              "docs/PULL_REQUEST_TEMPLATE.md", ".github/pull_request_template.md",
                              "pull_request_template.md", ".github/PULL_REQUEST_TEMPLATE"],
}
NOT_COLLECTED = [
    "secret-history scan (run a scanner such as gitleaks/trufflehog over full history - MANUAL blocker before going public)",
    "personal/private file review before a public flip (MANUAL blocker)",
    "README prose quality beyond shape metrics (agent-judged by reading it)",
    "topic accuracy/relevance (agent-judged)",
    "issue/PR triage responsiveness (agent-judged from recent activity)",
    "required-status-check names vs actual CI check names (agent-verified)",
]


def gh(args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["gh", *args], capture_output=True, text=True)
    except (OSError, FileNotFoundError):
        print(json.dumps({"error": "gh CLI not found"}))
        sys.exit(1)


def gh_json(args: list[str]):
    proc = gh(args)
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout.strip() or "null")
    except json.JSONDecodeError:
        return None


def readme_shape(text: str) -> dict:
    lines = text.splitlines()
    return {
        "lines": len(lines),
        "words": len(text.split()),
        "has_h1": bool(re.search(r"^#\s+\S", text, re.M)),
        "badges_top": len(re.findall(r"!\[[^\]]*\]\([^)]+\)", "\n".join(lines[:15]))),
        "code_block_first_60_lines": any(l.lstrip().startswith(("```", "~~~")) for l in lines[:60]),
    }


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    local = target is None
    meta = gh_json(["repo", "view", *([target] if target else []), "--json", VIEW_FIELDS])
    if meta is None:
        print(json.dumps({"error": "cannot read repo (gh repo view failed)"}))
        return 1
    repo = meta["nameWithOwner"]
    evidence: dict = {"repo": repo, "collected_via": "local+api" if local else "api",
                      "not_collected": NOT_COLLECTED}

    # In local mode file checks run from the git toplevel, not whatever cwd is.
    root = Path(".")
    if local:
        top = gh_top = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                                      capture_output=True, text=True)
        if gh_top.returncode == 0 and top.stdout.strip():
            root = Path(top.stdout.strip())

    # Custom social preview: GraphQL has the authoritative field; fall back to the
    # URL heuristic (custom uploads are served from repository-images).
    owner, name = repo.split("/", 1)
    og = gh_json(["api", "graphql", "-f", f"query=query{{repository(owner:\"{owner}\",name:\"{name}\")"
                  "{usesCustomOpenGraphImage}}", "--jq", ".data.repository.usesCustomOpenGraphImage"])
    if og is None:
        og = True if "repository-images" in (meta.get("openGraphImageUrl") or "") else None

    evidence["metadata"] = {
        "description": meta.get("description"),
        "description_length": len((meta.get("description") or "").strip()),
        "topics": [t.get("name") for t in (meta.get("repositoryTopics") or [])],
        "homepage": meta.get("homepageUrl") or None,
        "custom_social_preview": og,
        "private": meta.get("isPrivate"),
        "license": (meta.get("licenseInfo") or {}).get("key") or None,
    }
    ci_run = gh_json(["run", "list", "--repo", repo, "--limit", "1",
                      "--json", "conclusion,workflowName"])
    evidence["vital_signs"] = {
        "archived": meta.get("isArchived"),
        "pushed_at": meta.get("pushedAt"),
        "latest_release": (meta.get("latestRelease") or {}).get("tagName"),
        "stars": meta.get("stargazerCount"),
        "forks": meta.get("forkCount"),
        "issues_enabled": meta.get("hasIssuesEnabled"),
        "discussions_enabled": meta.get("hasDiscussionsEnabled"),
        "latest_ci_run": (ci_run[0] if isinstance(ci_run, list) and ci_run else None),
    }

    profile = gh_json(["api", f"repos/{repo}/community/profile"])
    evidence["community_profile_health"] = (profile or {}).get("health_percentage")

    def exists(path: str):
        """True/False when confirmed; None when not determinable (auth/plan/network)."""
        if local:
            p = root / path
            if p.is_file() and p.stat().st_size > 0:
                return True
            name_only = Path(path).name
            return any((base / name_only).is_file() and (base / name_only).stat().st_size > 0
                       for base in (root, root / ".github", root / "docs"))
        proc = gh(["api", f"repos/{repo}/contents/{path}", "--jq", ".path"])
        if proc.returncode == 0:
            return True
        return False if "404" in (proc.stderr or "") else None

    evidence["files"] = {f: exists(f) for f in HEALTH_FILES}
    for key, candidates in MULTI_LOCATION.items():
        states = [exists(c) for c in candidates]
        evidence["files"][key] = (True if any(s is True for s in states)
                                  else (False if all(s is False for s in states) else None))

    def listing(path: str):
        if local:
            p = root / path
            return [f.name for f in p.iterdir() if f.is_file()] if p.is_dir() else []
        data = gh(["api", f"repos/{repo}/contents/{path}"])
        if data.returncode != 0:
            return [] if "404" in (data.stderr or "") else None
        try:
            entries = json.loads(data.stdout.strip() or "[]")
            return [e.get("name", "") for e in entries if isinstance(e, dict)]
        except json.JSONDecodeError:
            return None
    names = listing(".github/ISSUE_TEMPLATE")
    evidence["files"]["issue_forms"] = (None if names is None else
                                        len([n for n in names if n.endswith((".yml", ".yaml"))
                                             and not n.startswith("config.")]))
    evidence["files"]["issue_template_config"] = (None if names is None else
                                                  any(n.startswith("config.") for n in names))
    wf = listing(".github/workflows")
    evidence["files"]["workflows"] = None if wf is None else len([n for n in wf if n.endswith((".yml", ".yaml"))])

    # README shape - local file when present, otherwise the README API.
    readme_path = root / "README.md"
    if local and readme_path.is_file():
        evidence["readme"] = readme_shape(readme_path.read_text(encoding="utf-8", errors="replace"))
    else:
        data = gh_json(["api", f"repos/{repo}/readme"])
        if data and data.get("content"):
            try:
                evidence["readme"] = readme_shape(
                    base64.b64decode(data["content"]).decode("utf-8", errors="replace"))
            except (ValueError, KeyError):
                evidence["readme"] = None
        else:
            evidence["readme"] = None

    # Protections summary (best effort; null = not determinable).
    prot: dict = {}
    branch = (meta.get("defaultBranchRef") or {}).get("name", "main")
    rulesets = gh_json(["api", f"repos/{repo}/rulesets"])
    prot["active_branch_rulesets"] = (None if rulesets is None else
                                      len([r for r in rulesets if r.get("target") == "branch"
                                           and r.get("enforcement") == "active"]))
    classic = gh(["api", f"repos/{repo}/branches/{branch}/protection", "--jq", ".url"])
    prot["classic_protection"] = True if classic.returncode == 0 else (False if "404" in (classic.stderr or "") else None)
    sec = gh_json(["api", f"repos/{repo}", "--jq", ".security_and_analysis"])
    prot["secret_scanning"] = ((sec or {}).get("secret_scanning") or {}).get("status")
    prot["push_protection"] = ((sec or {}).get("secret_scanning_push_protection") or {}).get("status")
    alerts = gh(["api", f"repos/{repo}/vulnerability-alerts"])
    prot["dependabot_alerts"] = True if alerts.returncode == 0 else (False if "404" in (alerts.stderr or "") else None)
    # Alerts and security-update PRs are separate toggles - check both.
    fixes = gh_json(["api", f"repos/{repo}/automated-security-fixes", "--jq", ".enabled"])
    prot["dependabot_security_updates"] = fixes if isinstance(fixes, bool) else None
    if not meta.get("isPrivate"):
        pvr = gh_json(["api", f"repos/{repo}/private-vulnerability-reporting", "--jq", ".enabled"])
        prot["private_vulnerability_reporting"] = pvr if isinstance(pvr, bool) else None
    evidence["protections"] = prot

    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
