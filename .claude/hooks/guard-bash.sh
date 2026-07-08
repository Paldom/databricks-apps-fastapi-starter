#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash) — deny a short list of never-do commands.
# Exit 2 blocks the tool call; the reason on stderr is fed back to the agent.
# Scope honesty: this is an agent convenience guard, not a security boundary
# (regex guards are bypassable via aliases/functions); CI remains the real gate.
set -u

command -v jq >/dev/null 2>&1 || exit 0   # never block on our own missing dep
CMD=$(jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[ -n "$CMD" ] || exit 0

deny() { echo "$1" >&2; exit 2; }

# Quoted strings (commit messages, grep patterns) must not trip flag rules.
CMD_SAFE=$(printf '%s' "$CMD" | sed -E "s/'[^']*'//g; s/\"[^\"]*\"//g")

# 1. Quality-gate bypass
if echo "$CMD_SAFE" | grep -qE 'git[[:space:]]+commit[^|;&]*([[:space:]]--no-verify|[[:space:]]-[a-zA-Z]*n[a-zA-Z]*([[:space:]]|$))'; then
  deny "Blocked: 'git commit --no-verify' bypasses this repo's quality gates. Fix the failing checks, then commit normally."
fi

# 2. Force-push to main/master
if echo "$CMD_SAFE" | grep -qE 'git[[:space:]]+push[^|;&]*(--force|-f)[^|;&]*[[:space:]](origin[[:space:]]+)?(main|master)\b' \
   || echo "$CMD_SAFE" | grep -qE 'git[[:space:]]+push[^|;&]*[[:space:]]\+(main|master)\b'; then
  deny "Blocked: force-pushing main/master rewrites shared history. Push a feature branch instead."
fi

# 3. Bare pip / python -m pip outside uv (command position only — 'uv run
#    python', 'grep pip' and 'which pip' stay legal)
if echo "$CMD" | grep -qE '(^|[;&|][[:space:]]*)pip3?[[:space:]]+install\b'; then
  deny "Blocked: bare 'pip install' breaks the uv-managed environment. Use 'cd backend && uv add <pkg>' (dev: 'uv add --dev <pkg>')."
fi
if echo "$CMD" | grep -qE '(^|[;&|][[:space:]]*)python3?[[:space:]]+-m[[:space:]]+pip\b'; then
  deny "Blocked: 'python -m pip' bypasses uv. Use 'uv add' / 'uv pip' from backend/."
fi

# 4. Recursive rm on repo root, home, cwd/parent, or wildcard — with or
#    without a trailing slash/star or quotes (rm -rf ~/, "/*", ./ ...).
if echo "$CMD" | grep -qE '(^|[;&|][[:space:]]*)rm[[:space:]]+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)[[:space:]]+["'"'"']?(/\*?|~/?\*?|\.\.?/?\*?|\*)["'"'"']?([[:space:]]|$)'; then
  deny "Blocked: recursive force-delete of a broad path. Delete specific paths explicitly."
fi

exit 0
