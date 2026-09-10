#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash): deny a short list of never-do commands.
# Exit 2 blocks the call and the stderr reason is fed back to the agent. Any crash
# or matcher error also exits 2 (fail closed). This is a denylist for agent
# convenience, not a security boundary; CI, rulesets and workspace permissions
# remain the real gate.
set -euo pipefail
trap 'echo "guard-bash crashed at: $BASH_COMMAND" >&2; exit 2' ERR

command -v jq >/dev/null 2>&1 || { echo "guard-bash: jq is required" >&2; exit 2; }
CMD=$(jq -r '.tool_input.command // empty')
[ -n "$CMD" ] || exit 0

deny() { echo "$1" >&2; exit 2; }

# Match against the whole command with a here-string (no pipe: a SIGPIPE from
# `grep -q` would otherwise turn a match into "no match" under pipefail).
has() {
  local status=0
  grep -Eq -- "$1" <<< "$CMD" || status=$?
  case "$status" in
    0) return 0 ;;
    1) return 1 ;;
    *) echo "guard-bash: matcher error ($status) for pattern: $1" >&2; exit 2 ;;
  esac
}

GIT='git\b[^|;&]*'   # allows global options such as `git -C backend`
DBX='databricks\b[^|;&]*'   # allows `databricks --profile x`

# 1. Quality-gate bypass
has "${GIT}\bcommit\b[^|;&]*(\s--no-verify\b|\s-[a-zA-Z]*n\b)" && deny "Blocked: 'git commit --no-verify' bypasses the commit gate. Fix the failing checks, then commit normally."
has '(^|[;&|]\s*)SKIP=\S+\s+git\b' && deny "Blocked: 'SKIP=<hook> git commit' skips part of the commit gate. Fix the failing hook instead."
has 'core\.hooksPath' && deny "Blocked: changing core.hooksPath disables the commit gate."
has 'pre-commit\s+uninstall' && deny "Blocked: uninstalling pre-commit disables the commit gate."

# 2. Force-push, or any push whose destination is main/master
has "${GIT}\bpush\b[^|;&]*(\s--force(-with-lease)?\b|\s-f\b)" && deny "Blocked: force-pushing rewrites shared history. Push a feature branch and open a PR."
has "${GIT}\bpush\b[^|;&]*(\s|:)\+?(main|master)\b" && deny "Blocked: pushing to main/master directly. Push a feature branch and open a PR."

# 3. Bare pip / python outside uv
has '(^|[;&|]\s*)pip3?\s+install\b' && deny "Blocked: bare 'pip install' breaks the uv-managed environment. Use 'uv add <pkg>' in backend/."
has '(^|[;&|]\s*)python3?\s+-m\s+pip\b' && deny "Blocked: 'python -m pip' bypasses uv. Use 'uv add' inside backend/."

# 4. Recursive force-delete of a broad path (flags may be combined or separate)
has '(^|[;&|]\s*)rm\s+(-\S+\s+)*-\S*[rR]\S*\s+(-\S+\s+)*(/|~|\.|\*)(\s|$)' && deny "Blocked: recursive delete of a broad path. Delete specific paths explicitly."
has '(^|[;&|]\s*)rm\s+(-\S+\s+)*(/|~|\.|\*)(\s|$)' && deny "Blocked: deleting a broad path. Delete specific paths explicitly."

# 5. Databricks: only the dev target may be deployed or run from an agent session
has "${DBX}\bbundle\s+(deploy|run|destroy)\b[^|;&]*(\s(-t|--target)(\s+|=)|--target=)(staging|prod)\b" && deny "Blocked: staging/prod deployments are a human action (workflow_dispatch behind an environment). Use '-t dev'."
has "${DBX}\bbundle\s+destroy\b" && deny "Blocked: 'bundle destroy' is a human action. Remove resources from the bundle and deploy instead."
has "${DBX}\bapps\s+delete\b" && deny "Blocked: deleting apps is a human action."

exit 0
