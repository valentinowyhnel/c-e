#!/bin/bash
set -euo pipefail

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

PASS=0; FAIL=0; WARN=0

pass() { echo "    $1"; ((PASS++)) || true; }
fail() { echo "    $1"; ((FAIL++)) || true; }
warn() { echo "  ~  $1"; ((WARN++)) || true; }

have_cmd() { command -v "$1" >/dev/null 2>&1; }

run_sentinel_tests() {
  if have_cmd uv; then
    uv sync >/dev/null
    uv run pytest tests/ -v --tb=short
    return
  fi
  if have_cmd docker; then
    docker run --rm \
      -v "$(pwd):/app" \
      -w /app \
      python:3.12-slim \
      bash -lc "pip install --no-cache-dir uv >/dev/null && uv sync >/dev/null && uv run pytest tests/ -v --tb=short"
    return
  fi
  echo "ni uv ni docker disponibles"
  return 1
}

extract_model_id() {
  python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("model_id",""))' 2>/dev/null || true
}

echo ""
echo ""
echo "   GATE  SYSTEME IMMUNITAIRE v2               "
echo ""

echo ""
echo "[ Tests unitaires Sentinel ]"
cd services/cortex-sentinel
run_sentinel_tests >/dev/null 2>&1 && pass "Tests sentinel passes" || fail "Tests sentinel echoues"
cd ../..

echo ""
echo "[ DaemonSet cortex-sentinel ]"
NODE_COUNT=$(kubectl get nodes --no-headers 2>/dev/null | wc -l | tr -d ' ')
RUNNING=$(kubectl get pods -n cortex-system -l app.kubernetes.io/name=cortex-sentinel --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l | tr -d ' ')
[ "$RUNNING" -eq "$NODE_COUNT" ] && pass "Sentinel Running ($RUNNING/$NODE_COUNT noeuds)" || fail "Sentinel insuffisants ($RUNNING/$NODE_COUNT)"

echo ""
echo "[ Trust Engine v2 ]"
kubectl port-forward -n cortex-system svc/cortex-trust-engine 18085:8080 &>/dev/null &
PF=$!
sleep 3

CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:18085/trust/evaluate/v2 -H "Content-Type: application/json" -d '{"entity_id":"gate-test","entity_type":"machine","evidences":[{"signal_type":"suspicious_process","source":"psutil_process","severity":0.7,"confidence":0.7,"ttl_seconds":300}]}' 2>/dev/null)
[ "$CODE" = "200" ] && pass "POST /trust/evaluate/v2 200" || fail "POST /trust/evaluate/v2 $CODE"

CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:18085/trust/sot/issue -H "Content-Type: application/json" -d '{"entity_id":"gate-sot","entity_type":"machine","reasons":["test"],"score":45.0}' 2>/dev/null)
[ "$CODE" = "200" ] && pass "POST /trust/sot/issue 200" || fail "POST /trust/sot/issue $CODE"

kill $PF 2>/dev/null || true

echo ""
echo "[ MCP Tools apoptose ]"
kubectl port-forward -n cortex-system svc/cortex-mcp-server 18080:8080 &>/dev/null &
PF=$!
sleep 2
for tool in issue_sot forensic_preserve get_blast_radius; do
  R=$(curl -s -X POST http://localhost:18080/mcp/debug/route -H "Content-Type: application/json" -d "{\"task\":\"$tool\",\"input\":\"test\"}" 2>/dev/null | extract_model_id)
  [ -n "$R" ] && pass "Tool $tool routable $R" || warn "Tool $tool non routable"
done
kill $PF 2>/dev/null || true

echo ""
echo "[ Falco rules ]"
kubectl get configmap cortex-falco-rules -n cortex-system &>/dev/null && pass "ConfigMap falco-rules presente" || fail "ConfigMap falco-rules absente"

echo ""
echo ""
printf "  PASS: %d  FAIL: %d  WARN: %d\n" $PASS $FAIL $WARN
echo ""
[ "$FAIL" -eq "0" ] && echo "  Gate immune v2 PASSED  pret Phase 7" && exit 0
echo "  $FAIL test(s) a corriger" && exit 1
