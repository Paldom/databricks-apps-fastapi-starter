#!/usr/bin/env bash
# PostToolUse hook (matcher: Edit|Write): lint/format only the file just edited.
# Exit 2 cannot undo the edit; it feeds the failure back so the agent fixes it.
# Keep this sub-second: it runs synchronously on every matching tool call.
set -euo pipefail
trap 'echo "lint-edited-file crashed at: $BASH_COMMAND" >&2; exit 2' ERR

command -v jq >/dev/null 2>&1 || { echo "lint-edited-file: jq is required" >&2; exit 2; }
FILE_PATH=$(jq -r '.tool_input.file_path // empty')
[ -n "$FILE_PATH" ] && [ -f "$FILE_PATH" ] || exit 0

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

case "$FILE_PATH" in
  "$ROOT"/backend/*.py|"$ROOT"/notebooks/*.py)
    if ! OUT=$(uv run --frozen --directory "$ROOT/backend" ruff check --fix --color never "$FILE_PATH" 2>&1); then
      echo "ruff found problems in $FILE_PATH it could not auto-fix:" >&2
      echo "$OUT" | tail -60 >&2
      exit 2
    fi
    uv run --frozen --directory "$ROOT/backend" ruff format "$FILE_PATH" >/dev/null 2>&1 || true
    ;;
  "$ROOT"/frontend/src/*.ts|"$ROOT"/frontend/src/*.tsx)
    PRETTIER="$ROOT/frontend/node_modules/.bin/prettier"
    [ -x "$PRETTIER" ] && "$PRETTIER" --log-level silent --write "$FILE_PATH" >/dev/null 2>&1 || true
    ;;
  *)
    # Other file types are covered by the Stop gate (pre-commit over the change set).
    ;;
esac

exit 0
