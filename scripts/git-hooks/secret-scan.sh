#!/usr/bin/env bash
# Block commits containing known API key patterns.
# Tracked + framework-managed (pre-commit `local` hook) so it survives clones
# and `pre-commit install` — unlike a raw .git/hooks/ script.
set -e

STAGED=$(git diff --cached --name-only --diff-filter=ACM)
[ -z "$STAGED" ] && exit 0

# High-confidence patterns — known prefixes that are almost never false positives.
PATTERNS=(
  'sk-ant-[a-zA-Z0-9_-]{20,}'     # Anthropic API keys
  'sk-proj-[a-zA-Z0-9_-]{20,}'    # OpenAI project keys
  'sk-[a-zA-Z0-9]{40,}'           # OpenAI legacy keys
  'AKIA[0-9A-Z]{16}'              # AWS access key IDs
  'ghp_[a-zA-Z0-9]{36}'           # GitHub personal tokens
  'gho_[a-zA-Z0-9]{36}'           # GitHub OAuth tokens
  'xox[baprs]-[a-zA-Z0-9-]{10,}'  # Slack tokens
)

for pattern in "${PATTERNS[@]}"; do
  if git diff --cached -U0 | grep -E "$pattern" > /dev/null; then
    echo "✗ BLOCKED: staged diff contains a pattern matching $pattern"
    echo "  Move the secret to .env and ensure .env is in .gitignore."
    exit 1
  fi
done

exit 0
