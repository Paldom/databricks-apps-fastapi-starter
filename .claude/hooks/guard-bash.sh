#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash): deny a short list of never-do commands.
# Exit 2 blocks the call and the stderr reason is fed back to the agent. Any crash
# also exits 2 (fail closed). This is a denylist for agent convenience, not a
# security boundary; CI, rulesets and workspace permissions remain the real gate.
set -euo pipefail
trap 'echo "guard-bash crashed at: $BASH_COMMAND" >&2; exit 2' ERR

command -v jq >/dev/null 2>&1 || { echo "guard-bash: jq is required" >&2; exit 2; }
CMD=$(jq -r '.tool_input.command // empty')
[ -n "$CMD" ] || exit 0

deny() { echo "$1" >&2; exit 2; }
has() { echo "$CMD" | grep -qE "$1"; }

# 1. Quality-gate bypass
has 'git\s+commit[^|;&]*(\s--no-verify|\s-[a-zA-Z]*n)' && deny "Blocked: 'git commit --no-verify' bypasses the commit gate. Fix the failing checks, then commit normally."
has '(^|[;&|]\s*)SKIP=\S+\s+git\s+commit\b' && deny "Blocked: 'SKIP=<hook> git commit' skips part of the commit gate. Fix the failing hook instead."
has 'core\.hooksPath' && deny "Blocked: changing core.hooksPath disables the commit gate."
has 'pre-commit\s+uninstall' && deny "Blocked: uninstalling pre-commit disables the commit gate."

# 2. Force-push or direct push to main/master
has 'git\s+push[^|;&]*(\s--force(-with-lease)?|\s-f\b)' && deny "Blocked: force-pushing rewrites shared history. Push a feature branch and open a PR."
has 'git\s+push[^|;&]*\s\+?(origin\s+)?(main|master)\b' && deny "Blocked: pushing to main/master directly. Push a feature branch and open a PR."

# 3. Bare pip / python outside uv
has '(^|[;&|]\s*)pip3?\s+install\b' && deny "Blocked: bare 'pip install' breaks the uv-managed environment. Use 'uv add <pkg>' in backend/."
has '(^|[;&|]\s*)python3?\s+-m\s+pip\b' && deny "Blocked: 'python -m pip' bypasses uv. Use 'uv add' inside backend/."

# 4. Recursive rm on broad paths
has '(^|[;&|]\s*)rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\s+(/|~|\.|\*)(\s|$)' && deny "Blocked: recursive force-delete of a broad path. Delete specific paths explicitly."

# 5. Databricks: only the dev target may be deployed or run from an agent session
has 'databricks\s+bundle\s+(deploy|run|destroy)\b[^|;&]*(\s(-t|--target)(\s+|=)|--target=)(staging|prod)\b' && deny "Blocked: staging/prod deployments are a human action (workflow_dispatch behind an environment). Use '-t dev'."
has 'databricks\s+bundle\s+destroy\b' && deny "Blocked: 'bundle destroy' is a human action. Remove resources from the bundle and deploy instead."
has 'databricks\s+apps\s+delete\b' && deny "Blocked: deleting apps is a human action."

exit 0
