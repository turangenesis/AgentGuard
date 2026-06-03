#!/usr/bin/env bash
# Enforce conventional commit prefixes.
# Tracked + framework-managed (pre-commit `commit-msg` hook) so it survives
# clones and `pre-commit install` — unlike a raw .git/hooks/ script.
# pre-commit passes the commit-message file path as $1.
MSG_FILE="$1"
FIRST_LINE=$(head -n 1 "$MSG_FILE")

# Allow merge commits and reverts to pass through.
if echo "$FIRST_LINE" | grep -qE '^(Merge |Revert )'; then
  exit 0
fi

# Required prefixes from the kit conventions.
if ! echo "$FIRST_LINE" | grep -qE '^(feature|fix|refactor|docs|chore|perf|test|ci): .+'; then
  echo "✗ Commit message must start with one of:"
  echo "    feature: | fix: | refactor: | docs: | chore: | perf: | test: | ci:"
  echo ""
  echo "  Your message: $FIRST_LINE"
  exit 1
fi

exit 0
