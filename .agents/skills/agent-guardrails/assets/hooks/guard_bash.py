#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash): deny a short list of never-do commands.

Exit 2 blocks the call; the reason on stderr is fed back to the agent. Commands are
lexed (shlex), split on `;`, `&&`, `||`, `|`, `&` and newlines, unwrapped through
sudo/env/time/nohup and one level of `bash -c '...'`, so `git -C . commit -n`,
`git push origin HEAD:main --force` and `python3.12 -m pip install x` are all seen
for what they are. Stdlib only — no jq. Unparseable input never blocks (exit 0).

Scope honesty: this guards the *agent's* Bash tool as a convenience. Aliases,
`eval`, and other tools route around it; server-side rulesets and CI stay the
real gate. Extend DENY_RULES rather than the parser when a new pattern bites.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

MAIN_REF_RE = re.compile(r"(^|:)(refs/heads/)?(main|master)$")
OPERATORS = {";", "&&", "||", "|", "&", ";;"}
GROUPING = {"(", ")", "{", "}", "((", "))"}
WRAPPERS = {"sudo", "command", "nohup", "time", "env", "doas"}
# Shell keywords that can stand in front of a command inside one segment.
KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "(", "exec"}
WRAPPER_VALUE_FLAGS = {"-u", "-g", "--user", "--group"}
GIT_VALUE_OPTS = {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
PYTHON_RE = re.compile(r"^python(3(\.\d+)?)?$")
PIP_RE = re.compile(r"^pip3?(\.\d+)?$")
BROAD_PATHS = {"/", "~", ".", "*", "..", "$HOME", "${HOME}"}


def lex(command: str) -> list[str]:
    lx = shlex.shlex(command, posix=True, punctuation_chars=True)
    lx.whitespace_split = True
    try:
        return list(lx)
    except ValueError:
        return command.split()


def segments(toks: list[str]) -> list[list[str]]:
    out: list[list[str]] = [[]]
    for t in toks:
        if t in OPERATORS or t in GROUPING or (t and set(t) <= set(";&|(){}")):
            if out[-1]:
                out.append([])
        else:
            out[-1].append(t)
    return [s for s in out if s]


def strip_wrappers(toks: list[str]) -> list[str]:
    i = 0
    while i < len(toks):
        t = toks[i]
        base = t.rsplit("/", 1)[-1]
        if t in KEYWORDS:
            i += 1
            continue
        if base in WRAPPERS:
            i += 1
            while i < len(toks) and (toks[i].startswith("-") or (base == "env" and "=" in toks[i])):
                i += 2 if toks[i] in WRAPPER_VALUE_FLAGS else 1
            continue
        if "=" in t and not t.startswith("-") and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            i += 1  # leading VAR=value assignment (also `SKIP=hook git commit`)
            continue
        break
    return toks[i:]


def leading_assignments(toks: list[str]) -> list[str]:
    """VAR=value words before the command (after wrappers)."""
    out = []
    for t in toks:
        if t.rsplit("/", 1)[-1] in WRAPPERS or t.startswith("-"):
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            out.append(t)
        else:
            break
    return out


def git_call(toks: list[str]):
    """(subcommand, args, git_options) if this segment is a git call, else (None, [], [])."""
    toks = strip_wrappers(toks)
    if not toks or toks[0].rsplit("/", 1)[-1] != "git":
        return None, [], []
    j, opts = 1, []
    while j < len(toks) and toks[j].startswith("-"):
        if toks[j] in GIT_VALUE_OPTS and j + 1 < len(toks):
            opts.append(f"{toks[j]} {toks[j + 1]}")
            j += 2
        else:
            opts.append(toks[j])
            j += 1
    if j >= len(toks):
        return None, [], opts
    return toks[j], toks[j + 1 :], opts


def is_force_flag(t: str) -> bool:
    return t == "--force" or bool(re.match(r"^-[a-zA-Z]*f[a-zA-Z]*$", t))


COMMIT_BOOL_SHORTS = set("aspvqneioz")  # short flags that take no value; -u/-m/-c/-C/-F/-S/-t do


def has_noverify(args: list[str]) -> bool:
    # git accepts unambiguous abbreviations of long options: --no-verif, --no-ver, ...
    # A short cluster counts only if every letter is a boolean flag (`-an`), so
    # `-uno` (= --untracked-files=no) is not mistaken for -n.
    for t in args:
        if t == "-n" or (t.startswith("--no-v") and "--no-verify".startswith(t)):
            return True
        if re.match(r"^-[a-zA-Z]+$", t) and "n" in t and set(t[1:]) <= COMMIT_BOOL_SHORTS:
            return True
    return False


def check_git(sub: str, args: list[str], opts: list[str], assignments: list[str]) -> str | None:
    hooks_off = any(re.search(r"core\.hooks[Pp]ath=", o) for o in opts) or any(
        a.startswith("--hooksPath=") for a in args
    )
    if sub == "commit" and (has_noverify(args) or hooks_off):
        return (
            "Blocked: `git commit --no-verify` (or -n, or a redirected core.hooksPath) bypasses "
            "this repo's quality gates. Fix the failing checks, then commit normally."
        )
    if sub == "commit" and any(a.startswith("SKIP=") for a in assignments):
        return (
            "Blocked: `SKIP=<hook> git commit` skips part of the commit gate. Fix the failing hook; "
            "SKIP is a human escape hatch, not an agent one."
        )
    if sub == "push":
        forced = any(
            is_force_flag(t)
            for t in args
            if t.startswith("-")
            and not t.startswith("--force-with-lease")
            and not t.startswith("--force-if-includes")
        )
        positionals: list[str] = []
        k = 0
        while k < len(args):
            t = args[k]
            if t in ("-o", "--push-option", "--repo", "--receive-pack", "--exec"):
                k += 2
                continue
            if t.startswith("-"):
                k += 1
                continue
            positionals.append(t)
            k += 1
        refspecs = positionals[1:]  # positionals[0] is the remote
        plus_main = any(r.startswith("+") and MAIN_REF_RE.search(r[1:]) for r in refspecs)
        target_main = any(MAIN_REF_RE.search(r.lstrip("+")) for r in refspecs)
        if plus_main or (forced and (target_main or not refspecs)):
            return (
                "Blocked: force-pushing main/master (or a force push with no explicit branch) "
                "rewrites shared history. Push a feature branch, or use --force-with-lease on a "
                "branch you own."
            )
    return None


def check_segment(toks: list[str]) -> str | None:
    inner = strip_wrappers(toks)
    if inner and inner[0].rsplit("/", 1)[-1] in SHELLS:  # one level of `bash -c '...'`
        for idx in range(1, len(inner)):
            t = inner[idx]
            if re.match(r"^-[a-zA-Z]+$", t) and "c" in t and idx + 1 < len(inner):
                for line in inner[idx + 1].splitlines():
                    for seg in segments(lex(line)):
                        verdict = check_segment(seg)
                        if verdict:
                            return verdict
                break
    sub, args, opts = git_call(toks)
    if sub:
        return check_git(sub, args, opts, leading_assignments(toks))
    if not inner:
        return None
    cmd = inner[0].rsplit("/", 1)[-1]
    # Bare pip / python -m pip outside uv (command position only: `uv run python`,
    # `grep pip` and `which pip` stay legal).
    if (
        PIP_RE.match(cmd)
        and len(inner) > 1
        and inner[1] == "install"
        and not {"-h", "--help"} & set(inner)
    ):
        return (
            "Blocked: bare `pip install` breaks the uv-managed environment. Use `uv add <pkg>` "
            "(or `uv add --dev <pkg>`)."
        )
    if PYTHON_RE.match(cmd) and len(inner) > 2 and inner[1] == "-m" and PIP_RE.match(inner[2]):
        return "Blocked: `python -m pip` bypasses uv. Use `uv add` / `uv pip` inside the project environment."
    # Recursive force-delete of a broad path.
    if cmd == "rm":
        flags = [t for t in inner[1:] if t.startswith("-")]
        paths = [t for t in inner[1:] if not t.startswith("-")]
        recursive = any("r" in f.lower() for f in flags) or "--recursive" in flags
        force = any("f" in f for f in flags if not f.startswith("--")) or "--force" in flags
        if recursive and force and any(p in BROAD_PATHS for p in paths):
            return (
                "Blocked: recursive force-delete of a broad path. Delete specific paths explicitly."
            )
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0  # unparseable event: never block on our own bug
    command = (payload.get("tool_input") or {}).get("command") or ""
    for line in command.splitlines():
        for seg in segments(lex(line)):
            verdict = check_segment(seg)
            if verdict:
                sys.stderr.write(verdict + "\n")
                return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
