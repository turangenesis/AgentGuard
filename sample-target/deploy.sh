#!/usr/bin/env bash
# Deployment script for taskflow-api.
# AgentGuard requires human approval before an agent deploys to production.
set -euo pipefail

TARGET="${1:-staging}"

echo "Building taskflow-api..."
npm run build

echo "Deploying to ${TARGET}..."
case "$TARGET" in
  staging)
    echo "  -> rsync dist/ to staging host"
    ;;
  production)
    echo "  -> rsync dist/ to production host"
    echo "  -> restarting production service"
    ;;
  *)
    echo "unknown target: $TARGET" >&2
    exit 1
    ;;
esac

echo "Done."
