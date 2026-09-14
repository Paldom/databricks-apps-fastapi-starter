#!/usr/bin/env bash
# Stop hook: refuse to end the turn while the commit gate would reject the change set.
# Parity rule: this runs pre-commit itself (commit and pre-push stages) over the files
# changed since the merge base with main plus untracked files, the same gate `git commit`
# and `git push` run. Exit 2 means "keep working". Crashes and timeouts also exit 2 (fail
# closed). The stop_hook_active guard is mandatory: on the retry round we re-verify and,
# if still failing, release with the failure reported through systemMessage so it is
# visible, never silently.
set -euo pipefail
trap 'echo "stop-verify crashed at: $BASH_COMMAND" >&2; exit 2' ERR

command -v jq >/dev/null 2>&1 || { echo "stop-verify: jq is required" >&2; exit 2; }
INPUT=$(cat)
ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"
cd "$ROOT"
DEADLINE=250   # seconds, below the 300 s hook timeout (a timed-out hook is non-blocking)

release_or_block() {
  local reason=$1 details=${2:-}
  if [ "$ACTIVE" = "true" ]; then
    jq -cn --arg m "stop-verify: still failing after a fix round; releasing to avoid a loop. NOT verified: $reason $(echo "$details" | tail -20)" '{systemMessage: $m}'
    exit 0
  fi
  echo "$reason" >&2
  [ -n "$details" ] && echo "$details" | tail -60 >&2
  exit 2
}

[ -f .pre-commit-config.yaml ] || exit 0

if command -v pre-commit >/dev/null 2>&1; then PC=(pre-commit)
elif uv run --frozen --project backend pre-commit --version >/dev/null 2>&1; then PC=(uv run --frozen --project backend pre-commit)
else
  release_or_block "this repo has a commit gate (.pre-commit-config.yaml) but pre-commit is not runnable. Run 'make setup'."
fi

# Change set: committed-but-unmerged + working tree changes (NUL-safe), plus untracked files.
# Deletions cannot be passed as files, so any deletion widens the run to --all-files.
SCOPE=(--all-files)
if BASE=$(git merge-base origin/main HEAD 2>/dev/null || git merge-base main HEAD 2>/dev/null); then
  FILES=()
  while IFS= read -r -d '' f; do [ -f "$f" ] && FILES+=("$f"); done < <(
    { git diff -z --name-only --diff-filter=ACMR "$BASE" --; git ls-files -z --others --exclude-standard; } | sort -zu)
  DELETED=$(git diff --name-only --diff-filter=D "$BASE" -- | wc -l)
  if [ "${#FILES[@]}" -eq 0 ] && [ "$DELETED" -eq 0 ]; then exit 0; fi
  if [ "$DELETED" -eq 0 ]; then SCOPE=(--files "${FILES[@]}"); fi
else
  echo "stop-verify: no merge base with main; verifying all files" >&2
fi

# One overall deadline for both stages; perl alarm is a portable `timeout`.
run_gate() {
  perl -e 'alarm shift; exec @ARGV or exit 2' -- "$1" bash -c '
    set -o pipefail
    PC=$1; shift
    if ! $PC run --hook-stage pre-commit "$@" >/dev/null 2>&1; then
      # detect-secrets rewrites its baseline (line numbers) and then insists it is staged.
      if ! git diff --quiet -- .secrets.baseline; then git add .secrets.baseline; fi
      $PC run --hook-stage pre-commit "$@" || exit 1
    fi
    $PC run --hook-stage pre-push "$@" || exit 1
  ' _ "${PC[*]}" "${SCOPE[@]}"
}

START=$SECONDS
OUT=""; STATUS=0
OUT=$(run_gate "$DEADLINE" 2>&1) || STATUS=$?
if [ "$STATUS" -eq 0 ]; then exit 0; fi
if [ $((SECONDS - START)) -ge "$DEADLINE" ]; then
  release_or_block "the commit gate timed out after ${DEADLINE}s; run 'make check' and fix before finishing."
fi
release_or_block "pre-commit would reject this change set, the same gate git runs. Fix, or run '${PC[*]} run --files <file>...' (and --hook-stage pre-push) until green:" "$OUT"
