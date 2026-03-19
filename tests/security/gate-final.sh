#!/bin/bash
set -euo pipefail

PASS=0
FAIL=0

pass() { echo "  PASS - $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }

echo ""
echo "CORTEX GATE PLATEFORME COMPLETE"
echo ""

kubectl get pods -n cortex-system --field-selector=status.phase=Running --no-headers | wc -l | grep -qv "^0$" \
  && pass "services cortex running" || fail "services cortex not running"
kubectl get pods -n vault-system --field-selector=status.phase=Running --no-headers | wc -l | grep -qv "^0$" \
  && pass "vault running" || fail "vault down"
kubectl get pods -n spire-system --field-selector=status.phase=Running --no-headers | wc -l | grep -qv "^0$" \
  && pass "spire running" || fail "spire down"

if kubectl get svc cortex-envoy -n cortex-system >/dev/null 2>&1; then
  kubectl port-forward -n cortex-system svc/cortex-envoy 18080:8080 >/tmp/cortex-envoy-port-forward.log 2>&1 &
  PF_PID=$!
  sleep 5
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer invalid-test-token" http://127.0.0.1:18080/protected || echo "000")
  [ "$CODE" != "200" ] \
    && pass "envoy fail closed invalid token (${CODE})" || fail "envoy open with invalid token"
  kill "$PF_PID" >/dev/null 2>&1 || true
  wait "$PF_PID" 2>/dev/null || true
else
  fail "envoy service introuvable"
fi

for agent in cortex-vllm cortex-sentinel cortex-mcp-server cortex-orchestrator cortex-obs-agent cortex-nats-bridge; do
  kubectl get deploy "$agent" -n cortex-system >/dev/null 2>&1 \
    && pass "$agent deployed" || fail "$agent absent"
done

kubectl get deploy cortex-console -n cortex-system >/dev/null 2>&1 \
  && pass "console deployed" || fail "console absent"
kubectl get deploy opentelemetry-collector -n cortex-system >/dev/null 2>&1 \
  && pass "otel collector deployed" || fail "otel collector absent"
kubectl get deploy cortex-victoriametrics -n cortex-system >/dev/null 2>&1 \
  && pass "victoriametrics deployed" || fail "victoriametrics absent"

kubectl get deploy cortex-approval -n cortex-system >/dev/null 2>&1 \
  && pass "approval deployed" || fail "approval absent"
kubectl get deploy cortex-audit -n cortex-system >/dev/null 2>&1 \
  && pass "audit deployed" || fail "audit absent"

echo ""
printf "PASS: %d  FAIL: %d\n" "$PASS" "$FAIL"

if [ "$FAIL" -eq 0 ]; then
  echo "PLATEFORME : PRETE POUR LE PREMIER CLIENT ENTERPRISE"
  exit 0
fi

echo "PLATEFORME : NON PRETE ($FAIL tests echoues)"
exit 1
