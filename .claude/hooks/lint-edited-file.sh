#!/usr/bin/env bash
# PostToolUse hook (matcher: Edit|Write) — ruff-check/format ONLY the backend
# Python file just edited. Exit 2 cannot undo the edit (it already happened);
# it feeds the failure back into the agent's context so it self-corrects
# immediately. Frontend/docs/other files exit 0 instantly — this hook must
# never slow down non-backend work. Keep it sub-second: it runs synchronously
# on every matching tool call.
set -u

command -v jq >/dev/null 2>&1 || exit 0
FILE_PATH=$(jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -n "$FILE_PATH" ] && [ -f "$FILE_PATH" ] || exit 0   # tool may have errored

# Repo root = two levels up from this script (.claude/hooks/ -> repo).
PROJ=$(cd "$(dirname "$0")/../.." && pwd) || exit 0
BACKEND="$PROJ/backend"

case "$FILE_PATH" in
  "$BACKEND"/*.py) ;;   # backend Python — lint it
  *) exit 0 ;;          # anything else — stay out of the way
esac

cd "$BACKEND" || exit 0

# --fix + format: auto-repair what is mechanical, report what is not.
# --force-exclude honours pyproject excludes (e.g. alembic/versions).
OUT=$(uv run ruff check --fix --force-exclude "$FILE_PATH" 2>&1) || {
  echo "ruff found problems in $FILE_PATH it could not auto-fix:" >&2
  echo "$OUT" >&2
  exit 2
}
OUT=$(uv run ruff format --force-exclude "$FILE_PATH" 2>&1) || {
  echo "ruff format failed on $FILE_PATH:" >&2
  echo "$OUT" >&2
  exit 2
}

exit 0
