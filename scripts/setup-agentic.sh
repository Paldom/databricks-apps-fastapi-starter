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

mkdir -p .agents/skills

if [[ "${1:-}" == "--update" ]]; then
  npx --yes skills update -y -p
else
  # Capture the lock entries before the CLI can change the lockfile.
  skill_entries="$(node <<'NODE'
const fs = require('fs');
const lock = JSON.parse(fs.readFileSync('skills-lock.json', 'utf8'));
const entries = Object.entries(lock.skills);
for (const [name, { source }] of entries) {
  if (!name || typeof source !== 'string' || !source || /[\t\r\n]/.test(name + source)) {
    throw new Error('Invalid skill name or source in skills-lock.json');
  }
}
for (const [name, { source }] of entries) {
  process.stdout.write(`${name}\t${source}\n`);
}
NODE
  )"

  if ! npx --yes skills experimental_install; then
    printf 'Lock restore failed; installing each skill from its recorded source.\n' >&2
    while IFS=$'\t' read -r skill_name source; do
      [[ -n "$skill_name" ]] || continue
      npx --yes skills add "$source" -s "$skill_name" -a '*' -y
    done <<< "$skill_entries"
  fi
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

if ! cmp -s AGENTS.md .github/copilot-instructions.md; then
  cp AGENTS.md .github/copilot-instructions.md
fi

printf '\nNext steps:\n  uv run --project backend pre-commit install --install-hooks\n'
