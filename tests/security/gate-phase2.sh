#!/bin/bash
set -euo pipefail

PASS=0
FAIL=0

pass() { echo "  PASS - $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }

echo ""
echo "CORTEX GATE PHASE 2"
echo ""

[ -f "services/cortex-sync/go.mod" ] && pass "cortex-sync present" || fail "cortex-sync absent"
[ -f "services/cortex-auth/go.mod" ] && pass "cortex-auth present" || fail "cortex-auth absent"
[ -f "services/cortex-trust-engine/pyproject.toml" ] && pass "cortex-trust-engine present" || fail "cortex-trust-engine absent"
[ -f "helm/cortex-identity/Chart.yaml" ] && pass "identity chart present" || fail "identity chart absent"
[ -f "scripts/setup-identity.sh" ] && pass "setup identity present" || fail "setup identity absent"

kubectl get deploy keycloak -n cortex-system >/dev/null 2>&1 && pass "keycloak deployed" || fail "keycloak absent"
kubectl get deploy lldap -n cortex-system >/dev/null 2>&1 && pass "lldap deployed" || fail "lldap absent"
kubectl get statefulset cortex-valkey -n cortex-system >/dev/null 2>&1 && pass "valkey deployed" || fail "valkey absent"

kubectl get pod -n cortex-system -l app=keycloak --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "keycloak running" || fail "keycloak non running"
kubectl get pod -n cortex-system -l app=lldap --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "lldap running" || fail "lldap non running"
kubectl get pod -n cortex-system -l app=cortex-valkey --field-selector=status.phase=Running --no-headers | grep -q Running \
  && pass "valkey running" || fail "valkey non running"

KEYCLOAK_POD=$(kubectl get pod -n cortex-system -l app=keycloak -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "$KEYCLOAK_POD" ]; then
  kubectl exec -n cortex-system "$KEYCLOAK_POD" -- /opt/keycloak/bin/kcadm.sh config credentials \
    --server http://127.0.0.1:8080 --realm master --user admin --password admin-change-me >/dev/null 2>&1 \
    && pass "keycloak api reachable" || fail "keycloak api inaccessible"
else
  fail "keycloak pod introuvable"
fi

LLDAP_POD=$(kubectl get pod -n cortex-system -l app=lldap -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -n "$LLDAP_POD" ]; then
  kubectl exec -n cortex-system "$LLDAP_POD" -- /app/lldap healthcheck >/dev/null 2>&1 \
    && pass "lldap healthcheck" || fail "lldap healthcheck echec"
else
  fail "lldap pod introuvable"
fi

echo ""
printf "PASS: %d  FAIL: %d\n" "$PASS" "$FAIL"

if [ "$FAIL" -eq 0 ]; then
  echo "GATE PHASE 2 : PASSED"
  exit 0
fi

echo "GATE PHASE 2 : FAILED"
exit 1
