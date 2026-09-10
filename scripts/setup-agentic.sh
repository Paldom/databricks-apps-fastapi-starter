#!/usr/bin/env bash
set -euo pipefail

# Run from any directory on macOS/Linux, or from Git Bash on Windows.
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$repo_root"

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--update" ) ]]; then
  printf 'Usage: %s [--update]\n' "$0" >&2
  exit 2
fi

for command_name in node npx; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Error: %s is required. Install Node.js 22 and try again.\n' "$command_name" >&2
    exit 1
  fi
done

SKILLS_CLI_VERSION="${SKILLS_CLI_VERSION:-1.5.25}"
mkdir -p .agents/skills

if [[ "${1:-}" == "--update" ]]; then
  npx --yes skills@"$SKILLS_CLI_VERSION" update -y -p
else
  # Restore the pinned skill set from skills-lock.json (fails loudly rather than fetching unpinned upstream).
  npx --yes skills@"$SKILLS_CLI_VERSION" experimental_install
fi

printf '\nDatabricks AI Dev Kit installs Databricks skills into .agents/skills and the databricks Claude Code plugin; .ai-dev-kit/version records the expected version.\n'
printf '%s\n' 'bash <(curl -sL https://raw.githubusercontent.com/databricks-solutions/ai-dev-kit/main/install.sh)'

for agent_dir in .claude .github .gemini .cursor .opencode; do
  mkdir -p -- "$agent_dir"
  mirror="$agent_dir/skills"
  if [[ -L "$mirror" ]]; then
    if [[ "$(readlink "$mirror")" == '../.agents/skills' ]]; then
      continue
    fi
    rm -- "$mirror"
  elif [[ -d "$mirror" ]]; then
    if ! rmdir -- "$mirror" 2>/dev/null; then
      printf 'Warning: leaving %s in place; directory is nonempty or cannot be removed.\n' "$mirror" >&2
      continue
    fi
  elif [[ -e "$mirror" ]]; then
    printf 'Warning: leaving %s in place; it is neither a symlink nor an empty directory.\n' "$mirror" >&2
    continue
  fi
  ln -s -- ../.agents/skills "$mirror"
done


printf '\nNext steps:\n  uv run --project backend pre-commit install --install-hooks\n'
