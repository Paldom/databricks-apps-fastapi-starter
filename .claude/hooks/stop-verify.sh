#!/usr/bin/env bash
# Stop hook: refuse to end the turn while the commit gate would reject the change set.
# Parity rule: this runs pre-commit itself (commit and pre-push stages) over the files
# changed since the merge base with main plus untracked files, the same gate `git commit`
# and `git push` run. Exit 2 means "keep working". Crashes and timeouts also exit 2 (fail
# closed). The stop_hook_active guard is mandatory: on the retry round we re-verify but
# release with an explicit "NOT verified" message, so the hook never loops.
set -euo pipefail
trap 'echo "stop-verify crashed at: $BASH_COMMAND" >&2; exit 2' ERR

command -v jq >/dev/null 2>&1 || { echo "stop-verify: jq is required" >&2; exit 2; }
INPUT=$(cat)
ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"
cd "$ROOT"

block() {
  if [ "$ACTIVE" = "true" ]; then
    echo "stop-verify: still failing after a fix round; releasing to avoid a loop. NOT verified: $1" >&2
    exit 0
  fi
  echo "$1" >&2
  [ -n "${2:-}" ] && echo "$2" | tail -60 >&2
  exit 2
}

[ -f .pre-commit-config.yaml ] || exit 0

if command -v pre-commit >/dev/null 2>&1; then PC="pre-commit"
elif uv run --frozen --directory backend pre-commit --version >/dev/null 2>&1; then PC="uv run --frozen --directory backend pre-commit"
else
  block "this repo has a commit gate (.pre-commit-config.yaml) but pre-commit is not runnable. Run 'make setup'."
fi

BASE=$(git merge-base origin/main HEAD 2>/dev/null || git merge-base main HEAD 2>/dev/null || echo HEAD)
FILES=$( { git diff --name-only --diff-filter=ACMR "$BASE" -- 2>/dev/null
           git ls-files --others --exclude-standard 2>/dev/null; } | sort -u | while read -r f; do [ -f "$f" ] && echo "$f"; done )
[ -z "$FILES" ] && exit 0

# perl alarm as a portable timeout: a hook that hits the harness timeout is non-blocking,
# so we fail closed just before it.
gate() { printf '%s\n' "$FILES" | tr '\n' '\0' | xargs -0 perl -e 'alarm 240; exec @ARGV' -- $PC run --hook-stage "$1" --files; }  # $PC unquoted on purpose

run_stage() {
  local stage=$1 out
  gate "$stage" >/dev/null 2>&1 && return 0
  # Auto-fix hooks exit non-zero after repairing the tree; the second run is the verdict.
  if out=$(gate "$stage" 2>&1); then return 0; fi
  local code=$?
  [ "$code" -eq 142 ] && block "the commit gate ($stage stage) timed out after 240s; run 'make check' and fix before finishing."
  block "pre-commit ($stage stage) would reject this change set, the same gate git runs. Fix, or run '$PC run --hook-stage $stage --files <file>...' until green:" "$out"
}

run_stage pre-commit
run_stage pre-push
exit 0
