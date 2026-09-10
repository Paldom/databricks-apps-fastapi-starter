#!/usr/bin/env python3
"""Read-only audit of a repo's agent-guardrail setup (Claude Code hooks,
settings scopes, rules files). Never modifies anything.

Usage: python3 check_guardrails.py [--root PATH]

Exit codes: 0 = no errors (warnings allowed), 1 = defects found.
Output: one `OK|WARN|ERROR <area>: <detail>` line per finding.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

KNOWN_TOOLS = {  # built-in tool names per https://code.claude.com/docs/en/hooks (2026-09)
    "Bash",
    "PowerShell",
    "Edit",
    "Write",
    "NotebookEdit",
    "Read",
    "Glob",
    "Grep",
    "Agent",
    "Workflow",
    "WebFetch",
    "WebSearch",
    "AskUserQuestion",
    "ExitPlanMode",
    "Skill",
    "ToolSearch",
}
# Events where exit 2 blocks (docs table). PostToolUse is deliberately absent: exit 2
# there is feedback only.
BLOCKABLE_EVENTS = {
    "PreToolUse",
    "UserPromptSubmit",
    "UserPromptExpansion",
    "Stop",
    "SubagentStop",
    "TeammateIdle",
    "TaskCreated",
    "TaskCompleted",
    "ConfigChange",
    "WorktreeCreate",
}
INTERPRETERS = ("python3", "python", "bash", "sh", "node", "uv")
KNOWN_EVENTS = {  # https://code.claude.com/docs/en/hooks (2026-09): 33 events
    "SessionStart",
    "Setup",
    "UserPromptSubmit",
    "UserPromptExpansion",
    "PreToolUse",
    "PermissionRequest",
    "PermissionDenied",
    "PostToolUse",
    "PostToolUseFailure",
    "PostToolBatch",
    "Notification",
    "MessageDisplay",
    "SubagentStart",
    "SubagentStop",
    "TaskCreated",
    "TaskCompleted",
    "Stop",
    "StopFailure",
    "TeammateIdle",
    "InstructionsLoaded",
    "ConfigChange",
    "CwdChanged",
    "DirectoryAdded",
    "FileChanged",
    "WorktreeCreate",
    "WorktreeRemove",
    "PreCompact",
    "PostCompact",
    "PreModelSwitch",
    "PostModelSwitch",
    "Elicitation",
    "ElicitationResult",
    "SessionEnd",
}

errors = 0
warnings = 0


def report(level: str, area: str, msg: str) -> None:
    global errors, warnings
    if level == "ERROR":
        errors += 1
    elif level == "WARN":
        warnings += 1
    print(f"{level:5s} {area}: {msg}")


def check_settings_file(path: Path, root: Path) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        report(
            "ERROR",
            str(path),
            f"unreadable or invalid JSON ({exc}) — the whole file is ignored silently",
        )
        return
    if not isinstance(data, dict):
        report("ERROR", str(path), f"settings must be a JSON object, got {type(data).__name__}")
        return
    hooks = data.get("hooks")
    if hooks is None:
        report("OK", str(path), "valid JSON, no hooks key")
        return
    if not isinstance(hooks, dict):
        report("ERROR", str(path), '"hooks" must be an object keyed by event name')
        return
    for event, groups in hooks.items():
        if event not in KNOWN_EVENTS:
            hint = next((e for e in KNOWN_EVENTS if e.lower() == event.lower()), None)
            report(
                "ERROR",
                str(path),
                f"hooks.{event!r} is not a hook event"
                + (f" (did you mean {hint!r}?)" if hint else "")
                + " — it never fires",
            )
        if not isinstance(groups, list):
            report(
                "ERROR",
                str(path),
                f"hooks.{event} must be a LIST of matcher groups — got {type(groups).__name__} (wrong nesting fails silently)",
            )
            continue
        for gi, group in enumerate(groups):
            where = f"hooks.{event}[{gi}]"
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                report(
                    "ERROR",
                    str(path),
                    f'{where} needs an inner "hooks" ARRAY of handlers (three-level nesting)',
                )
                continue
            matcher = group.get("matcher", "")
            if isinstance(matcher, str) and matcher and re.fullmatch(r"[A-Za-z0-9_|, ]+", matcher):
                for tool in re.split(r"[|,]", matcher):
                    tool = tool.strip()
                    if (
                        tool
                        and tool not in KNOWN_TOOLS
                        and tool.lower() in {t.lower() for t in KNOWN_TOOLS}
                    ):
                        report(
                            "ERROR",
                            str(path),
                            f"{where} matcher {tool!r} — matchers are case-sensitive; this never fires (did you mean {next(t for t in KNOWN_TOOLS if t.lower() == tool.lower())!r}?)",
                        )
            for hi, h in enumerate(group.get("hooks") or []):
                if not isinstance(h, dict):
                    continue
                cmd = h.get("command", "")
                hwhere = f"{where}.hooks[{hi}]"
                if h.get("type") == "command" and cmd:
                    if "$HOME" in cmd:
                        report(
                            "WARN",
                            str(path),
                            f"{hwhere} uses $HOME — may not expand; use $CLAUDE_PROJECT_DIR for project scripts",
                        )
                    m = re.search(r"\$CLAUDE_PROJECT_DIR[\"']?(/[^\s\"']+)", cmd)
                    if m:
                        script = root / m.group(1).lstrip("/")
                        # `python3 "$CLAUDE_PROJECT_DIR/..."` needs no executable bit; a bare path does.
                        via_interpreter = (
                            cmd.strip().strip("\"'").split()[0].rsplit("/", 1)[-1] in INTERPRETERS
                        )
                        if not script.is_file():
                            report(
                                "ERROR",
                                str(path),
                                f"{hwhere} points at missing script {m.group(1)}",
                            )
                        elif not via_interpreter and not os.access(script, os.X_OK):
                            report(
                                "ERROR",
                                str(path),
                                f"{hwhere} script {m.group(1)} is not executable (chmod +x) — hook fails silently",
                            )
                        else:
                            check_hook_script(script, event, root)
                    if "timeout" not in h and event == "PostToolUse":
                        report(
                            "WARN",
                            str(path),
                            f"{hwhere} has no timeout — PostToolUse hooks run in the hot path; set a small explicit timeout",
                        )


def check_hook_script(script: Path, event: str, root: Path) -> None:
    try:
        text = script.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    # exit 1 used where a block was clearly intended
    for lineno, line in enumerate(text.splitlines(), 1):
        if re.search(r"\b(exit 1|return 1|sys\.exit\(1\))\b", line) and re.search(
            r"block|deny|fail|refus", text, re.I
        ):
            report(
                "WARN",
                str(script),
                f"line {lineno}: exit code 1 does NOT block — only exit 2 does (or decision JSON on stdout); plain text with any other code is logged and the action proceeds",
            )
            break
    if event == "Stop" and "stop_hook_active" not in text:
        report(
            "ERROR",
            str(script),
            "Stop hook without a stop_hook_active guard — this loops the first time verification cannot be fixed immediately",
        )
    if (
        event == "Stop"
        and (root / ".pre-commit-config.yaml").is_file()
        and "pre-commit" not in text
    ):
        report(
            "WARN",
            str(script),
            "repo has .pre-commit-config.yaml but the Stop gate never runs pre-commit — the agent can sign off changes the commit hook will reject (parity gap)",
        )
    if "jq " in text and "command -v jq" not in text:
        report(
            "WARN",
            str(script),
            "uses jq without checking it exists — on machines without jq the hook fails silently "
            "(the shipped hooks are stdlib Python for exactly this reason)",
        )
    # Only lines where the ruff call is real code (before any quote or comment): a
    # hint string that *mentions* `ruff check --fix` must not trip this.
    if event == "PostToolUse" and re.search(
        r"^[^\"'#]*\bruff (check )?--fix|^[^\"'#]*\bruff format(?! --check)", text, re.M
    ):
        report(
            "WARN",
            str(script),
            "PostToolUse hook rewrites the file (ruff --fix / format) — the agent's next edit hits "
            "the stale-file check; report here, auto-fix at pre-commit or in the Stop gate",
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    args = ap.parse_args()
    root = args.root.resolve()

    # settings scopes
    proj = root / ".claude" / "settings.json"
    local = root / ".claude" / "settings.local.json"
    if proj.is_file():
        check_settings_file(proj, root)
    else:
        report(
            "WARN", str(proj), "no committed project settings — no team-shared hooks are installed"
        )
    if local.is_file():
        check_settings_file(local, root)
        gi = root / ".gitignore"
        if not (gi.is_file() and "settings.local.json" in gi.read_text(errors="replace")):
            report(
                "ERROR",
                str(local),
                "settings.local.json exists but is not gitignored — personal config will be committed",
            )

    # orphaned hook scripts
    hooks_dir = root / ".claude" / "hooks"
    if hooks_dir.is_dir():
        wired = ""
        for f in (proj, local):
            if f.is_file():
                wired += f.read_text(errors="replace")
        for script in sorted(hooks_dir.iterdir()):
            if script.is_file() and script.name not in wired:
                report(
                    "WARN",
                    str(script),
                    "hook script present but not referenced by any settings file — dead code or missing wiring",
                )

    # rules files
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"
    if agents.is_file():
        n = len(agents.read_text(errors="replace").splitlines())
        if n > 250:
            report(
                "WARN",
                str(agents),
                f"{n} lines — rules files past ~200 lines are token overhead the model increasingly ignores; trim",
            )
        else:
            report("OK", str(agents), f"present ({n} lines)")
        if claude.is_file() and "@AGENTS.md" not in claude.read_text(errors="replace"):
            report(
                "WARN",
                str(claude),
                "CLAUDE.md exists but does not import AGENTS.md — two rule files will drift; make one canonical",
            )
    elif claude.is_file():
        report(
            "OK",
            str(claude),
            "CLAUDE.md present (consider AGENTS.md as the vendor-neutral canonical file)",
        )
    else:
        report("WARN", str(root), "no AGENTS.md or CLAUDE.md — the agent has no repo rules at all")

    print(f"{'FAIL' if errors else 'OK'}: {errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
