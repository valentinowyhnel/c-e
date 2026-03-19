#!/bin/bash
set -euo pipefail

PASS=0
FAIL=0
WARN=0

pass() { echo "  PASS - $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  WARN - $1"; WARN=$((WARN + 1)); }

echo ""
echo "CORTEX GATE - PRODUCTION HARDENING"
echo ""

python scripts/runtime/check-production-maturity.py >/tmp/cortex-production-maturity.log 2>&1 \
  && pass "production maturity registry clear" \
  || warn "production maturity blockers present ($(tr '\n' ' ' </tmp/cortex-production-maturity.log))"

kubectl get secret cortex-internal-api -n cortex-system >/dev/null 2>&1 \
  && pass "secret cortex-internal-api present" || fail "secret cortex-internal-api absent"

kubectl get secret cortex-console-internal -n cortex-system >/dev/null 2>&1 \
  && pass "secret cortex-console-internal present" || fail "secret cortex-console-internal absent"

check_internal_route() {
  local service="$1"
  local path="$2"
  local local_port="$3"

  kubectl port-forward -n cortex-system "svc/${service}" "${local_port}:8080" >/tmp/"${service}"-pf.log 2>&1 &
  local pf=$!
  sleep 4

  local without_token
  without_token=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${local_port}${path}" || echo "000")
  local token
  token=$(kubectl get secret cortex-internal-api -n cortex-system -o jsonpath='{.data.token}' 2>/dev/null | base64 -d || true)
  local with_token
  with_token=$(curl -s -o /dev/null -w "%{http_code}" -H "x-cortex-internal-token: ${token}" "http://127.0.0.1:${local_port}${path}" || echo "000")

  if [ "$without_token" = "401" ] || [ "$without_token" = "403" ]; then
    pass "${service} denies missing token (${without_token})"
  else
    fail "${service} missing-token response ${without_token}"
  fi

  if [ "$with_token" = "200" ]; then
    pass "${service} accepts valid token"
  else
    fail "${service} valid-token response ${with_token}"
  fi

  kill "$pf" >/dev/null 2>&1 || true
  wait "$pf" 2>/dev/null || true
}

check_internal_route "cortex-trust-engine" "/trust/profile/gate-prod" 18101
check_internal_route "cortex-approval" "/v1/requests" 18102
check_internal_route "cortex-audit" "/v1/events?limit=1" 18103
check_internal_route "cortex-obs-agent" "/v1/feed" 18104

check_no_dev_image() {
  local workload="$1"
  local image
  image=$(kubectl get deploy "$workload" -n cortex-system -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "")
  if echo "$image" | grep -Eq ':(dev|latest)$'; then
    fail "${workload} still uses non-production image tag (${image})"
  elif [ -n "$image" ]; then
    pass "${workload} uses pinned non-dev image (${image})"
  else
    warn "${workload} image not found"
  fi
}

check_no_dev_image "cortex-trust-engine"
check_no_dev_image "cortex-mcp-server"
check_no_dev_image "cortex-console"

echo ""
printf "PASS: %d  FAIL: %d  WARN: %d\n" "$PASS" "$FAIL" "$WARN"

if [ "$FAIL" -eq 0 ]; then
  echo "GATE PRODUCTION HARDENING : PASSED"
  exit 0
fi

echo "GATE PRODUCTION HARDENING : FAILED"
exit 1
