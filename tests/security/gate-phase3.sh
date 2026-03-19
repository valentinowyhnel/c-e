#!/bin/bash
set -euo pipefail

PASS=0
FAIL=0

pass() { echo "  PASS - $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }

echo ""
echo "CORTEX GATE PHASE 3"
echo ""

[ -f "services/cortex-gateway/go.mod" ] && pass "cortex-gateway present" || fail "cortex-gateway absent"
[ -f "services/cortex-graph/go.mod" ] && pass "cortex-graph present" || fail "cortex-graph absent"
[ -f "helm/cortex-enforcement/Chart.yaml" ] && pass "enforcement chart present" || fail "enforcement chart absent"
[ -f "scripts/setup-enforcement.sh" ] && pass "setup enforcement present" || fail "setup enforcement absent"

kubectl get deploy cortex-gateway -n cortex-system >/dev/null 2>&1 && pass "gateway deployed" || fail "gateway absent"
kubectl get deploy cortex-graph -n cortex-system >/dev/null 2>&1 && pass "graph deployed" || fail "graph absent"
kubectl get deploy cortex-opa -n cortex-system >/dev/null 2>&1 && pass "opa deployed" || fail "opa absent"
kubectl get deploy cortex-envoy -n cortex-system >/dev/null 2>&1 && pass "envoy deployed" || fail "envoy absent"
kubectl get statefulset cortex-neo4j -n cortex-system >/dev/null 2>&1 && pass "neo4j deployed" || fail "neo4j absent"

kubectl get pod -n cortex-system -l app=cortex-gateway --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "gateway running" || fail "gateway non running"
kubectl get pod -n cortex-system -l app=cortex-graph --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "graph running" || fail "graph non running"
kubectl get pod -n cortex-system -l app=cortex-opa --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "opa running" || fail "opa non running"
kubectl get pod -n cortex-system -l app=cortex-envoy --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "envoy running" || fail "envoy non running"
kubectl get pod -n cortex-system -l app=cortex-neo4j --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "neo4j running" || fail "neo4j non running"

kubectl port-forward -n cortex-system svc/cortex-envoy 10000:10000 >/tmp/cortex-envoy-port-forward.log 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT
sleep 5

CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:10000/protected || true)
[ "$CODE" = "403" ] && pass "envoy fail-closed sans token" || fail "envoy ouvert sans token ($CODE)"

echo ""
printf "PASS: %d  FAIL: %d\n" "$PASS" "$FAIL"

if [ "$FAIL" -eq 0 ]; then
  echo "GATE PHASE 3 : PASSED"
  exit 0
fi

echo "GATE PHASE 3 : FAILED"
exit 1
