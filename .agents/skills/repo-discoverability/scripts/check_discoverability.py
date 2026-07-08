#!/usr/bin/env python3
"""Read-only audit of GitHub-native discoverability levers.

Usage: check_discoverability.py [owner/repo]   (default: the repo for the cwd)
Prints PASS/WARN/FAIL lines per lever; exit 1 if any FAIL. Needs `gh` auth. Stdlib only.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

FIELDS = "name,description,repositoryTopics,homepageUrl,isPrivate,openGraphImageUrl"


def gh(args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["gh", *args], capture_output=True, text=True)
    except (OSError, FileNotFoundError):
        print("FAIL: gh CLI not found - install https://cli.github.com")
        sys.exit(1)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def main() -> int:
    target = sys.argv[1:2]
    proc = gh(["repo", "view", *target, "--json", FIELDS])
    if proc.returncode != 0:
        print(f"FAIL: cannot read repo: {proc.stderr.strip()}")
        return 1
    d = json.loads(proc.stdout)
    fails = 0

    def report(level: str, msg: str) -> None:
        nonlocal fails
        if level == "FAIL":
            fails += 1
        print(f"{level}: {msg}")

    desc = (d.get("description") or "").strip()
    if not desc:
        report("FAIL", "description missing - the About text is also GitHub's search snippet")
    elif len(desc) < 20:
        report("WARN", f"description is only {len(desc)} chars - say what/for whom/outcome")
    elif len(desc) > 350:
        report("WARN", f"description is {len(desc)} chars - GitHub truncates long About text")
    else:
        report("PASS", f"description set ({len(desc)} chars)")

    topics = [t.get("name", "") for t in (d.get("repositoryTopics") or [])]
    if not topics:
        report("FAIL", "no topics - topics are browsable search surfaces (aim for 5-10)")
    elif len(topics) < 5:
        report("WARN", f"only {len(topics)} topics ({', '.join(topics)}) - aim for 5-10 accurate ones")
    else:
        report("PASS", f"{len(topics)} topics: {', '.join(topics)}")

    if (d.get("homepageUrl") or "").strip():
        report("PASS", f"homepage set: {d['homepageUrl']}")
    else:
        report("WARN", "no homepage URL - link docs or a demo if one exists")

    # GraphQL has the authoritative custom-preview flag; fall back to the URL heuristic.
    name = d.get("name", "")
    owner_proc = gh(["repo", "view", *target, "--json", "owner", "--jq", ".owner.login"])
    custom = None
    if owner_proc.returncode == 0 and owner_proc.stdout.strip():
        q = f'query{{repository(owner:"{owner_proc.stdout.strip()}",name:"{name}"){{usesCustomOpenGraphImage}}}}'
        p2 = gh(["api", "graphql", "-f", f"query={q}", "--jq", ".data.repository.usesCustomOpenGraphImage"])
        if p2.returncode == 0 and p2.stdout.strip() in ("true", "false"):
            custom = p2.stdout.strip() == "true"
    if custom is None:
        custom = "repository-images" in (d.get("openGraphImageUrl") or "")
    if custom:
        report("PASS", "custom social preview image set")
    else:
        report("WARN", "default social preview - shared links render as bare name+avatar "
                       "(Settings -> General -> Social preview, 1280x640)")

    # H1 alignment: only checkable when a local README exists (cwd repo).
    readme = Path("README.md")
    if not target and readme.is_file():
        m = re.search(r"^#\s+(.+)$", readme.read_text(encoding="utf-8", errors="replace"), re.M)
        if not m:
            report("WARN", "local README has no H1 - repo name/H1 alignment not checkable")
        elif norm(d.get("name", "")) in norm(m.group(1)) or norm(m.group(1)) in norm(d.get("name", "")):
            report("PASS", f"README H1 ({m.group(1).strip()!r}) aligns with repo name")
        else:
            report("WARN", f"README H1 ({m.group(1).strip()!r}) does not match repo name "
                           f"({d.get('name')!r}) - align them or lead the description with the plain name")

    if d.get("isPrivate"):
        print("NOTE: repo is private - invisible to search until public; metadata prepared now pays off at the flip")

    print(f"{'FAIL' if fails else 'OK'}: {fails} failing lever(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
