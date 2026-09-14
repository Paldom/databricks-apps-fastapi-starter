#!/usr/bin/env python3
"""Stop hook: refuse to end the turn while the repo's own commit gate would reject it.

Parity rule: an agent may only sign off a change set the commit gate accepts. When
`.pre-commit-config.yaml` exists this runs pre-commit itself over the changed +
untracked files — the identical gate `git commit` runs, zero drift. Auto-fixing hooks
exit non-zero AFTER repairing the tree, so it runs twice and the second verdict counts.
Exit 2 on Stop means "keep working". The `stop_hook_active` guard is MANDATORY: on a
retry round we re-verify and release (exit 0) only when the failure output is unchanged
— no progress means the agent cannot fix it and must not loop; a changed failure keeps
blocking (the harness's own cap of 8 consecutive blocks stays the backstop). A release
is reported through `systemMessage` on stdout, because stderr on exit 0 only reaches the
debug log. Runs in $CLAUDE_PROJECT_DIR, not the shell's cwd. Stdlib only.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

# No pre-commit in this repo: ONE fast, project-specific verify command (seconds,
# not minutes — it runs at the end of every turn; the full suite belongs in CI).
VERIFY_CMD = ["uv", "run", "ruff", "check", "."]
# Examples: ["make", "check"] · ["uv", "run", "pytest", "-q", "-x", "tests/smoke"]
TIMEOUT = 240  # keep the settings.json timeout above this; a timed-out hook is a silent pass
TAIL = 30


def _state_file(root: str) -> str:
    key = hashlib.sha256(os.path.abspath(root).encode()).hexdigest()[:12]
    return os.path.join(tempfile.gettempdir(), f"verify_stop-{key}.txt")


def no_progress(root: str, output: str) -> bool:
    """True when this failure output equals the last blocked round's (nothing changed)."""
    digest = hashlib.sha256(
        output.encode(errors="replace")
    ).hexdigest()  # a fingerprint, not security
    path = _state_file(root)
    try:
        with open(path, encoding="utf-8") as fh:
            previous = fh.read().strip()
    except OSError:
        previous = ""
    with contextlib.suppress(OSError), open(path, "w", encoding="utf-8") as fh:
        fh.write(digest)
    return previous == digest


def clear_state(root: str) -> None:
    with contextlib.suppress(OSError):
        os.remove(_state_file(root))


def emit(message: str) -> None:
    sys.stderr.write(message + "\n")
    print(json.dumps({"systemMessage": message}))


def run(argv: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv, capture_output=True, text=True, timeout=TIMEOUT, cwd=cwd, check=False
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    active = bool(payload.get("stop_hook_active"))
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

    def block(reason: str, detail: str = "") -> int:
        tail = "\n".join(detail.splitlines()[-TAIL:])
        if active and no_progress(root, reason + detail):
            emit(
                "stop-verify: still failing after a fix round — releasing to avoid a loop. NOT verified: "
                + reason
                + ("\n" + tail if tail else "")
            )
            return 0
        sys.stderr.write(reason + ("\n" + tail if tail else "") + "\n")
        return 2

    try:
        if os.path.isfile(os.path.join(root, ".pre-commit-config.yaml")):
            if shutil.which("pre-commit"):
                pc = ["pre-commit"]
            elif (
                shutil.which("uv")
                and run(["uv", "run", "--no-sync", "pre-commit", "--version"], root).returncode == 0
            ):
                pc = ["uv", "run", "--no-sync", "pre-commit"]
            else:
                return block(
                    "this repo has a commit gate (.pre-commit-config.yaml) but pre-commit is not runnable. "
                    "Install it (uv add --dev pre-commit && uv run pre-commit install --install-hooks) and "
                    "run it on the changed files until green before finishing."
                )
            if run(["git", "rev-parse", "--verify", "HEAD"], root).returncode == 0:
                changed = run(
                    ["git", "diff", "--name-only", "--diff-filter=d", "HEAD", "--"], root
                ).stdout.split()
            else:  # unborn branch: everything tracked is new
                changed = run(["git", "ls-files"], root).stdout.split()
            untracked = run(
                ["git", "ls-files", "--others", "--exclude-standard"], root
            ).stdout.split()
            files = sorted(set(changed) | set(untracked))
            if not files:
                clear_state(root)
                return 0
            if run([*pc, "run", "--files", *files], root).returncode == 0:
                clear_state(root)
                return 0  # clean first pass
            second = run(
                [*pc, "run", "--files", *files], root
            )  # auto-fixers converge on the second run
            if second.returncode == 0:
                clear_state(root)
                return 0
            return block(
                "pre-commit would reject this change set — the same gate `git commit` runs. Fix, or run "
                f"`{' '.join(pc)} run --files <file>...` until green:",
                second.stdout + second.stderr,
            )
        proc = run(VERIFY_CMD, root)
        if proc.returncode == 0:
            clear_state(root)
            return 0
        return block(
            f"Verification failed ({' '.join(VERIFY_CMD)}). Fix before finishing:",
            proc.stdout + proc.stderr,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        emit(f"stop-verify: could not run the gate ({exc}) — NOT verified")
        return 0


if __name__ == "__main__":
    sys.exit(main())
