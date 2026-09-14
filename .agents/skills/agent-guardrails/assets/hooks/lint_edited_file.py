#!/usr/bin/env python3
"""PostToolUse hook (matcher: Edit|Write): ruff-check ONLY the Python file just edited.

Exit 2 cannot undo the edit (it already happened); it feeds the findings back into
the agent's context so it self-corrects immediately. This hook reports, it does not
rewrite: an in-place `--fix`/`format` here changes the file under the agent, and its
next Edit fails the stale-file check. Auto-fixing belongs to pre-commit and to the
Stop gate's second pass. Keep this sub-second: it runs on every matching tool call.
Stdlib only — no jq. Ruff comes from the project environment (`uv run ruff`), so the
version is the one pyproject/uv.lock pins; a repo without ruff skips silently.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

TIMEOUT = 20  # per ruff call; keep the settings.json timeout above 2x this


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not file_path.endswith((".py", ".pyi")):
        return 0
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    if not os.path.isabs(file_path):
        file_path = os.path.join(project_dir, file_path)
    if not os.path.isfile(file_path):
        return 0  # the tool may have errored

    if shutil.which("uv"):
        prefix = ["uv", "run", "--no-sync", "ruff"]
    elif shutil.which("ruff"):
        prefix = ["ruff"]
    else:
        return 0  # no ruff here: pre-commit/CI still enforce

    problems: list[str] = []
    for args, label in (
        (["check", "--force-exclude", "--output-format=concise"], "lint"),
        (["format", "--check", "--force-exclude"], "format"),
    ):
        try:
            proc = subprocess.run(
                [*prefix, *args, file_path],
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                cwd=project_dir,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            break  # tooling problem, not a code problem — keep what we already found
        if proc.returncode != 0:
            out = (proc.stdout or proc.stderr).strip()
            if "No module named ruff" in out or "not found" in out.lower():
                return 0  # ruff is not a dependency of this project
            problems.append(f"[{label}]\n{out}")
    if not problems:
        return 0
    sys.stderr.write("Ruff found problems in the file just written:\n" + "\n".join(problems) + "\n")
    sys.stderr.write(
        "Fix them now (`uv run ruff check --fix <file> && uv run ruff format <file>` handles most); "
        "do not add a blanket noqa to get past this.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
