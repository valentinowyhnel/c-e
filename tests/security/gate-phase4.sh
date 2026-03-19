#!/bin/bash
set -euo pipefail

PASS=0
FAIL=0

pass() { echo "  PASS - $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }

echo ""
echo "CORTEX GATE PHASE 4"
echo ""

[ -f "services/cortex-vllm/pyproject.toml" ] && pass "cortex-vllm present" || fail "cortex-vllm absent"
[ -f "services/cortex-sentinel/pyproject.toml" ] && pass "cortex-sentinel present" || fail "cortex-sentinel absent"
[ -f "services/cortex-mcp-server/pyproject.toml" ] && pass "cortex-mcp-server present" || fail "cortex-mcp-server absent"
[ -f "services/cortex-orchestrator/pyproject.toml" ] && pass "cortex-orchestrator present" || fail "cortex-orchestrator absent"
[ -f "helm/cortex-agents/Chart.yaml" ] && pass "agents chart present" || fail "agents chart absent"
[ -f "scripts/setup-agents.sh" ] && pass "setup agents present" || fail "setup agents absent"

kubectl get statefulset cortex-nats -n cortex-system >/dev/null 2>&1 && pass "nats deployed" || fail "nats absent"
kubectl get deploy cortex-vllm -n cortex-system >/dev/null 2>&1 && pass "vllm deployed" || fail "vllm absent"
kubectl get deploy cortex-sentinel -n cortex-system >/dev/null 2>&1 && pass "sentinel deployed" || fail "sentinel absent"
kubectl get deploy cortex-mcp-server -n cortex-system >/dev/null 2>&1 && pass "mcp server deployed" || fail "mcp server absent"
kubectl get deploy cortex-orchestrator -n cortex-system >/dev/null 2>&1 && pass "orchestrator deployed" || fail "orchestrator absent"

kubectl get pod -n cortex-system -l app=cortex-nats --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "nats running" || fail "nats non running"
kubectl get pod -n cortex-system -l app=cortex-vllm --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "vllm running" || fail "vllm non running"
kubectl get pod -n cortex-system -l app=cortex-sentinel --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "sentinel running" || fail "sentinel non running"
kubectl get pod -n cortex-system -l app=cortex-mcp-server --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "mcp server running" || fail "mcp server non running"
kubectl get pod -n cortex-system -l app=cortex-orchestrator --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "orchestrator running" || fail "orchestrator non running"

SENTINEL_POD=$(kubectl get pod -n cortex-system -l app=cortex-sentinel -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "$SENTINEL_POD" ]; then
  kubectl exec -n cortex-system "$SENTINEL_POD" -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health').read().decode())" >/dev/null 2>&1 \
    && pass "sentinel health reachable" || fail "sentinel health inaccessible"
else
  fail "sentinel pod introuvable"
fi

ORCH_POD=$(kubectl get pod -n cortex-system -l app=cortex-orchestrator -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "$ORCH_POD" ]; then
  kubectl exec -n cortex-system "$ORCH_POD" -- python -c "import urllib.request, json; req=urllib.request.Request('http://127.0.0.1:8080/v1/plan', data=json.dumps({'request_id':'plan-1','task':'classify_intent','payload':'hello','risk_level':2,'actions':['read_graph']}).encode(), headers={'Content-Type':'application/json'}); print(urllib.request.urlopen(req).status)" >/dev/null 2>&1 \
    && pass "orchestrator planning flow reachable" || fail "orchestrator planning flow inaccessible"
else
  fail "orchestrator pod introuvable"
fi

echo ""
printf "PASS: %d  FAIL: %d\n" "$PASS" "$FAIL"

if [ "$FAIL" -eq 0 ]; then
  echo "GATE PHASE 4 : PASSED"
  exit 0
fi

echo "GATE PHASE 4 : FAILED"
exit 1
