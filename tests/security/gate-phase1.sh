#!/bin/bash
set -euo pipefail

PASS=0
FAIL=0

pass() { echo "  PASS - $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }

echo ""
echo "CORTEX GATE PHASE 1"
echo ""

kubectl cluster-info >/dev/null 2>&1 && pass "cluster Kind accessible" || fail "cluster inaccessible"

kubectl get daemonset calico-node -n kube-system >/dev/null 2>&1 && pass "Calico node present" || fail "Calico absent"
kubectl get deployment calico-kube-controllers -n kube-system >/dev/null 2>&1 && pass "Calico controllers presents" || fail "Calico controllers absents"

for ns in cortex-system vault-system spire-system; do
  kubectl get namespace "$ns" >/dev/null 2>&1 && pass "namespace $ns" || fail "namespace $ns absent"
  kubectl get networkpolicy default-deny-all -n "$ns" >/dev/null 2>&1 && pass "default-deny-all $ns" || fail "default-deny-all absent dans $ns"
done

kubectl get pod -n vault-system -l app.kubernetes.io/name=vault --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "Vault running" || fail "Vault non running"

kubectl get auth/kubernetes/config >/dev/null 2>&1 || true

kubectl get pod -n spire-system -l app=spire-server --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "SPIRE server running" || fail "SPIRE server non running"
kubectl get pod -n spire-system -l app=spire-agent --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "SPIRE agent running" || fail "SPIRE agent non running"

echo ""
printf "PASS: %d  FAIL: %d\n" "$PASS" "$FAIL"

if [ "$FAIL" -eq 0 ]; then
  echo "GATE PHASE 1 : PASSED"
  exit 0
fi

echo "GATE PHASE 1 : FAILED"
exit 1
