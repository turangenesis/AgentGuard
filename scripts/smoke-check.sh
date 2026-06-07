#!/usr/bin/env bash
# smoke-check.sh — health check for Headroom
#
# Pre-implementation:  verifies kit + project scaffolding files exist.
# Post-implementation: ALSO runs the test suite once the package + deps exist.
#
# Usage:  bash scripts/smoke-check.sh
# Exit:   0 = all checks passed, 1 = one or more failed
# Safe to run anytime: read-only, no secrets needed.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

check_file() {
  if [ -f "$1" ]; then
    echo "  ✓  $1"; PASS=$((PASS + 1))
  else
    echo "  ✗  MISSING: $1"; FAIL=$((FAIL + 1))
  fi
}

echo ""
echo "=== Project scaffolding ==="
check_file "CLAUDE.md"
check_file "AGENTS.md"
check_file "README.md"
check_file "LICENSE"
check_file ".gitignore"
check_file ".env.example"

echo ""
echo "=== Core docs ==="
check_file "docs/ARCHITECTURE.md"
check_file "docs/TESTING.md"
check_file "docs/HANDOFF.md"
check_file "docs/VERIFICATION.md"
check_file "docs/PLANS/current-feature-plan.md"

echo ""
echo "=== Project code (activates once implemented) ==="
if [ -f "pyproject.toml" ] || [ -f "requirements.txt" ]; then
  echo "  dependencies detected — checking package + running tests"
  check_file "headroom/__init__.py"
  check_file "headroom/graph.py"
  check_file "headroom/policy/guardian.py"
  check_file "headroom/api.py"
  if command -v pytest >/dev/null 2>&1; then
    echo ""
    echo "=== pytest ==="
    if pytest -q; then
      echo "  ✓  pytest passed"; PASS=$((PASS + 1))
    else
      echo "  ✗  pytest failed"; FAIL=$((FAIL + 1))
    fi
  else
    echo "  !  pytest not installed — run: pip install -r requirements.txt"
  fi
else
  echo "  •  no pyproject.toml / requirements.txt yet — project not implemented."
  echo "     # TODO: package + pytest checks activate automatically once deps exist."
fi

echo ""
echo "═══════════════════════════════════════"
echo "  Passed: $PASS    Failed: $FAIL"
echo "═══════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "  SMOKE CHECK FAILED — fix the missing items before committing."
  echo ""
  exit 1
else
  echo ""
  echo "  SMOKE CHECK PASSED."
  echo ""
  exit 0
fi
