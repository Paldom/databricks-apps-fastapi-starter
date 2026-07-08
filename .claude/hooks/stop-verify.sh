#!/usr/bin/env bash
# Stop hook — refuse to end the turn while the backend quality gate fails.
# Exit 2 on Stop means "keep working"; the reason on stderr goes back to the
# agent. The harness force-overrides after 8 consecutive blocks. The
# stop_hook_active guard below is MANDATORY — without it this hook loops the
# first time the agent cannot immediately fix a failure.
#
# Scoping: the gate (~10-15s) runs only when the working tree has uncommitted
# backend Python work; frontend- or docs-only turns exit 0 in milliseconds.
set -u

command -v jq >/dev/null 2>&1 || exit 0
INPUT=$(cat)
ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null) || exit 0
[ "$ACTIVE" = "true" ] && exit 0   # already re-running because of us — let go

# Repo root = two levels up from this script (.claude/hooks/ -> repo).
PROJ=$(cd "$(dirname "$0")/../.." && pwd) || exit 0
cd "$PROJ" || exit 0

# Only gate backend Python work: uncommitted .py, project metadata, or
# migration changes under backend/. The optional trailing quote matches
# git's quoted-path output for names with spaces or non-ASCII characters.
CHANGED=$(git status --porcelain -- backend/ 2>/dev/null \
  | grep -E '\.py"?$|backend/pyproject\.toml"?$|backend/uv\.lock"?$|backend/alembic/' || true)
[ -n "$CHANGED" ] || exit 0

cd "$PROJ/backend" || exit 0
# Single source for the gate: the displayed string IS the executed command.
GATE='uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest --cov'
OUT=$(bash -c "$GATE" 2>&1) || {
  {
    echo "Stop blocked: the backend quality gate failed. Fix before finishing."
    echo "Gate (run from backend/): $GATE"
    echo "--- last 40 lines ---"
    echo "$OUT" | tail -40
  } >&2
  exit 2
}

exit 0
