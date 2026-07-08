#!/usr/bin/env python3
"""Read-only audit of GitHub repository protections.

Usage: check_protections.py [owner/repo]   (default: the repo for the cwd)
Prints PASS/WARN/FAIL/UNKNOWN per control; exit 1 if ANY FAIL is emitted
(unprotected default branch, PVR disabled on a public repo, ...). Degrades to
UNKNOWN on 403/404 (plan limits, missing admin) - unknown is not failure.
Needs `gh` auth. Stdlib only.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def gh(args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["gh", *args], capture_output=True, text=True)
    except (OSError, FileNotFoundError):
        print("FAIL: gh CLI not found - install https://cli.github.com")
        sys.exit(1)


def gh_json(args: list[str]):
    proc = gh(args)
    if proc.returncode != 0:
        return None, proc.stderr.strip()
    try:
        return json.loads(proc.stdout.strip() or "null"), None
    except json.JSONDecodeError:
        return None, "unparseable response"


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    view_args = ["repo", "view"] + ([target] if target else []) + \
        ["--json", "nameWithOwner,defaultBranchRef,isPrivate"]
    info, err = gh_json(view_args)
    if info is None:
        print(f"FAIL: cannot read repo: {err}")
        return 1
    repo = info["nameWithOwner"]
    branch = (info.get("defaultBranchRef") or {}).get("name", "main")
    private = bool(info.get("isPrivate"))
    print(f"repo: {repo} (default branch: {branch}, {'private' if private else 'public'})")

    # 1. Ruleset or classic protection on the default branch.
    protected = False
    unknowable = 0
    fails = 0
    rulesets, err = gh_json(["api", f"repos/{repo}/rulesets"])
    if rulesets is None:
        unknowable += 1
        print(f"UNKNOWN: rulesets not readable ({err or 'no access'})")
    else:
        hits = []
        for rs in rulesets:
            if rs.get("target") != "branch" or rs.get("enforcement") != "active":
                continue
            detail, _ = gh_json(["api", f"repos/{repo}/rulesets/{rs['id']}"])
            if not detail:
                continue
            refs = (detail.get("conditions") or {}).get("ref_name", {}).get("include", [])
            if "~DEFAULT_BRANCH" in refs or f"refs/heads/{branch}" in refs or "~ALL" in refs:
                rules = {r.get("type") for r in detail.get("rules", [])}
                hits.append((rs.get("name", f"id {rs['id']}"), rules))
        if hits:
            protected = True
            for name, rules in hits:
                print(f"PASS: active ruleset {name!r} covers {branch} (rules: {', '.join(sorted(rules))})")
                for want, label in (("pull_request", "require PR"),
                                    ("required_status_checks", "required status checks"),
                                    ("non_fast_forward", "block force pushes")):
                    if want not in rules:
                        print(f"WARN: ruleset {name!r} lacks {label}")
        else:
            print(f"WARN: no active ruleset targets {branch}")
    if not protected:
        classic, err = gh_json(["api", f"repos/{repo}/branches/{branch}/protection"])
        if classic:
            protected = True
            print(f"PASS: classic branch protection on {branch} (consider migrating to a ruleset)")
        elif err and "404" not in err.lower() and "not protected" not in err.lower():
            unknowable += 1
            print(f"UNKNOWN: classic protection not readable ({err.splitlines()[-1] if err else 'no access'})")
        else:
            fails += 1
            print(f"FAIL: {branch} has no ruleset and no classic protection")

    # 2. Secret scanning + push protection.
    sec, err = gh_json(["api", f"repos/{repo}", "--jq", ".security_and_analysis"])
    if not sec:
        print(f"UNKNOWN: security_and_analysis not readable ({err or 'hidden on this plan'})")
    else:
        for key, label in (("secret_scanning", "secret scanning"),
                           ("secret_scanning_push_protection", "push protection")):
            status = (sec.get(key) or {}).get("status")
            if status == "enabled":
                print(f"PASS: {label} enabled")
            elif status == "disabled":
                print(f"WARN: {label} disabled" + (" (needs GHAS/Secret Protection on private repos)" if private else ""))
            else:
                print(f"UNKNOWN: {label} status not visible")

    # 3. Dependabot.
    if Path(".github/dependabot.yml").is_file() and not target:
        print("PASS: .github/dependabot.yml present (local)")
    else:
        proc = gh(["api", f"repos/{repo}/contents/.github/dependabot.yml", "--jq", ".path"])
        print("PASS: .github/dependabot.yml present" if proc.returncode == 0
              else "WARN: no dependabot.yml - version updates are not configured")
    proc = gh(["api", f"repos/{repo}/vulnerability-alerts"])
    if proc.returncode == 0:
        print("PASS: Dependabot alerts enabled")
    elif "404" in (proc.stderr or ""):
        print("WARN: Dependabot alerts disabled")
    else:
        print("UNKNOWN: Dependabot alerts status needs admin access")

    # 4. Private vulnerability reporting (public repos only).
    if private:
        print("NOTE: private repo - private vulnerability reporting applies after going public")
    else:
        pvr, err = gh_json(["api", f"repos/{repo}/private-vulnerability-reporting", "--jq", ".enabled"])
        if pvr is True:
            print("PASS: private vulnerability reporting enabled")
        elif pvr is False:
            fails += 1
            print("FAIL: private vulnerability reporting disabled (SECURITY.md links will 404)")
        else:
            print(f"UNKNOWN: PVR status not readable ({err or 'no access'})")

    if not protected and unknowable >= 2:
        # Both checks were unreadable (typically 403 plan limits on a private
        # repo) - the status is not determinable, which is not the same as missing.
        print("UNKNOWN: protection status not determinable (plan limits or missing access) - "
              "on private repos, rulesets/branch protection need a paid plan")
    print(f"{'FAIL' if fails else 'OK'}: {fails} failing control(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
