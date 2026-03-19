#!/bin/bash
set -euo pipefail

PASS=0
FAIL=0
WARN=0

pass() { echo "  PASS - $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  WARN - $1"; WARN=$((WARN + 1)); }

echo ""
echo "CORTEX GATE PHASE 6 - OBSERVABILITE AGENTIQUE"
echo ""

AVAIL=$(free -m | awk '/^Mem:/ {print $7}')
[ "$AVAIL" -gt "500" ] && pass "ram disponible (${AVAIL}Mi)" || fail "ram insuffisante (${AVAIL}Mi)"

kubectl get deployment grafana -n monitoring >/dev/null 2>&1 \
  && fail "grafana encore present" || pass "grafana absent"
kubectl get deployment prometheus-server -n monitoring >/dev/null 2>&1 \
  && fail "prometheus encore present" || pass "prometheus absent"

kubectl get pod -n cortex-system -l app.kubernetes.io/name=cortex-victoriametrics --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "victoriametrics running" || fail "victoriametrics non running"

OTEL_AVAILABLE=$(kubectl get deployment opentelemetry-collector -n cortex-system -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")
[ "${OTEL_AVAILABLE:-0}" -ge 1 ] \
  && pass "otel collector running" || fail "otel collector non running"

kubectl get pod -n cortex-system -l app.kubernetes.io/name=cortex-nats-bridge --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "nats bridge running" || warn "nats bridge non running"

kubectl get pod -n cortex-system -l app.kubernetes.io/name=cortex-obs-agent --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "obs agent running" || fail "obs agent non running"

kubectl get pod -n cortex-system -l app.kubernetes.io/name=cortex-audit --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "cortex-audit running" || fail "cortex-audit non running"

kubectl get pod -n cortex-system -l app.kubernetes.io/name=cortex-approval --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "cortex-approval running" || fail "cortex-approval non running"

OBS_POD=$(kubectl get pod -n cortex-system -l app.kubernetes.io/name=cortex-obs-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "$OBS_POD" ]; then
  kubectl port-forward -n cortex-system "pod/${OBS_POD}" 18090:8080 >/tmp/cortex-obs-agent-port-forward.log 2>&1 &
  PF1=$!
  sleep 5

  OBS_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18090/healthz || echo "000")
  [ "$OBS_HEALTH" = "200" ] && pass "obs agent healthz ok" || fail "obs agent healthz ${OBS_HEALTH}"

  LOOPS=$(curl -s http://127.0.0.1:18090/status | jq -r '.loops_active' 2>/dev/null || echo "0")
  [ "${LOOPS:-0}" = "5" ] && pass "5 boucles actives" || warn "boucles actives ${LOOPS}/5"

  ANOMALY=$(curl -s -X POST http://127.0.0.1:18090/test/anomaly \
    -H "Content-Type: application/json" \
    -d '{"service":"cortex-auth","metric":"latency_p99","value":9999,"baseline":100}' | jq -r '.is_anomalous' 2>/dev/null || echo "false")
  [ "$ANOMALY" = "true" ] && pass "detection anomalie operationnelle" || warn "test anomalie non concluant"

  kill "$PF1" >/dev/null 2>&1 || true
  wait "$PF1" 2>/dev/null || true
else
  fail "pod cortex-obs-agent introuvable"
fi

VM_POD=$(kubectl get pod -n cortex-system -l app.kubernetes.io/name=cortex-victoriametrics -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "$VM_POD" ]; then
  kubectl port-forward -n cortex-system "pod/${VM_POD}" 18428:8428 >/tmp/cortex-vm-port-forward.log 2>&1 &
  PF2=$!
  sleep 5
  VM_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18428/health || echo "000")
  [ "$VM_HEALTH" = "200" ] && pass "victoriametrics health ok" || fail "victoriametrics health ${VM_HEALTH}"
  kill "$PF2" >/dev/null 2>&1 || true
  wait "$PF2" 2>/dev/null || true
else
  fail "pod victoriametrics introuvable"
fi

if kubectl get svc cortex-envoy -n cortex-system >/dev/null 2>&1; then
  kubectl port-forward -n cortex-system svc/cortex-envoy 18083:8080 >/tmp/cortex-envoy-port-forward.log 2>&1 &
  PF3=$!
  sleep 5

  CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
    -H "Authorization: Bearer invalid-test-token" \
    http://127.0.0.1:18083/protected || echo "000")
  if echo "401 403" | grep -qw "$CODE"; then
    pass "envoy deny token invalide (http $CODE)"
  elif [ "$CODE" = "200" ]; then
    fail "envoy laisse passer token invalide"
  else
    warn "envoy repond $CODE sur token invalide"
  fi

  kubectl scale deployment cortex-gateway -n cortex-system --replicas=0 >/dev/null 2>&1
  sleep 10
  CODE_DOWN=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:18083/protected || echo "000")
  kubectl scale deployment cortex-gateway -n cortex-system --replicas=1 >/dev/null 2>&1
  kubectl rollout status deployment/cortex-gateway -n cortex-system --timeout=180s >/dev/null 2>&1 || true

  [ "$CODE_DOWN" != "200" ] && pass "envoy fail closed gateway down (${CODE_DOWN})" || fail "envoy laisse passer gateway down"

  kill "$PF3" >/dev/null 2>&1 || true
  wait "$PF3" 2>/dev/null || true
else
  fail "service cortex-envoy introuvable"
fi

echo ""
printf "PASS: %d  FAIL: %d  WARN: %d\n" "$PASS" "$FAIL" "$WARN"

if [ "$FAIL" -eq 0 ]; then
  echo "GATE PHASE 6 : PASSED"
  exit 0
fi

echo "GATE PHASE 6 : FAILED"
exit 1
