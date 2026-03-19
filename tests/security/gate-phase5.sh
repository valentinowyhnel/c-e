#!/bin/bash
set -euo pipefail

PASS=0
FAIL=0

pass() { echo "  PASS - $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }

echo ""
echo "CORTEX GATE PHASE 5"
echo ""

[ -f "services/cortex-console/package.json" ] && pass "cortex-console package present" || fail "cortex-console package absent"
[ -f "services/cortex-console/app/page.tsx" ] && pass "dashboard page present" || fail "dashboard page absent"
[ -f "services/cortex-console/app/api/health/route.ts" ] && pass "console health route present" || fail "console health route absent"
[ -f "helm/cortex-console/Chart.yaml" ] && pass "console chart present" || fail "console chart absent"
[ -f "scripts/setup-console.sh" ] && pass "setup console present" || fail "setup console absent"

[ -f "services/cortex-console/package-lock.json" ] && pass "package lock present" || fail "package lock absent"

kubectl get deploy cortex-console -n cortex-system >/dev/null 2>&1 && pass "console deployed" || fail "console absent"
kubectl get svc cortex-console -n cortex-system >/dev/null 2>&1 && pass "console service deployed" || fail "console service absent"

kubectl get pod -n cortex-system -l app=cortex-console --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "console running" || fail "console non running"

helm lint helm/cortex-console --strict >/dev/null 2>&1 && pass "console chart lint" || fail "console chart lint failed"

POD_NAME=$(kubectl get pod -n cortex-system -l app=cortex-console -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "$POD_NAME" ]; then
  kubectl port-forward -n cortex-system "pod/${POD_NAME}" 3000:3000 >/tmp/cortex-console-port-forward.log 2>&1 &
  PF_PID=$!
  sleep 5

  curl -fsS http://127.0.0.1:3000/api/health >/dev/null 2>&1 \
    && pass "console health reachable" || fail "console health unreachable"
  ROOT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/)
  [ "$ROOT_STATUS" = "200" ] \
    && pass "console dashboard reachable" || fail "console dashboard unreachable"

  kill "$PF_PID" >/dev/null 2>&1 || true
  wait "$PF_PID" 2>/dev/null || true
else
  fail "console pod introuvable"
  fail "console HTTP validation skipped"
fi

echo ""
printf "PASS: %d  FAIL: %d\n" "$PASS" "$FAIL"

if [ "$FAIL" -eq 0 ]; then
  echo "GATE PHASE 5 : PASSED"
  exit 0
fi

echo "GATE PHASE 5 : FAILED"
exit 1
