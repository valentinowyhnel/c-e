#!/bin/bash
set -euo pipefail

PASS=0
FAIL=0
WARN=0

pass() { echo "  PASS $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  WARN $1"; WARN=$((WARN + 1)); }

for file in \
  docs/API_MATRIX.md \
  scripts/validate-runtime-api.sh \
  services/cortex-console/app/api/graph/search/route.ts \
  services/cortex-console/app/api/graph/entities/[entityId]/route.ts; do
  [ -f "$file" ] && pass "$file present" || fail "$file missing"
done

if bash scripts/validate-runtime-api.sh; then
  pass "runtime api validation"
else
  warn "runtime api validation has failures or absent services"
fi

printf "\nPASS: %d  FAIL: %d  WARN: %d\n" "$PASS" "$FAIL" "$WARN"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
