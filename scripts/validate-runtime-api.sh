#!/bin/bash
set -euo pipefail

NS="cortex-system"

start_port_forward() {
  local service="$1"
  local local_port="$2"
  local remote_port="$3"
  local path="${4:-/health}"
  local namespace="${5:-$NS}"

  kubectl port-forward -n "$namespace" "svc/${service}" "${local_port}:${remote_port}" >/tmp/"${service}-${local_port}".pf.log 2>&1 &
  local pf=$!

  for _ in $(seq 1 30); do
    if curl -s -o /dev/null "http://127.0.0.1:${local_port}${path}"; then
      echo "$pf"
      return 0
    fi
    sleep 1
  done

  kill "$pf" >/dev/null 2>&1 || true
  return 1
}

check_endpoint() {
  local name="$1"
  local service="$2"
  local local_port="$3"
  local remote_port="$4"
  local path="$5"
  local namespace="${6:-$NS}"

  if ! kubectl get svc -n "$namespace" "$service" >/dev/null 2>&1; then
    echo "WARN ${name}: service ${service} absent"
    return 0
  fi

  local pf
  if ! pf="$(start_port_forward "$service" "$local_port" "$remote_port" "$path" "$namespace")"; then
    echo "FAIL ${name}: 000000"
    return 1
  fi
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${local_port}${path}" || echo "000")"
  kill "$pf" >/dev/null 2>&1 || true

  if [ "$code" = "200" ] || [ "$code" = "202" ]; then
    echo "PASS ${name}: ${code}"
  else
    echo "FAIL ${name}: ${code}"
    return 1
  fi
}

FAIL=0

check_endpoint "graph health" "cortex-graph" 18084 8080 "/health" || FAIL=$((FAIL + 1))
check_endpoint "graph overview" "cortex-graph" 18084 8080 "/v1/graph/overview" || FAIL=$((FAIL + 1))
check_endpoint "auth health" "cortex-auth" 18085 8080 "/health" || FAIL=$((FAIL + 1))
check_endpoint "sync health" "cortex-sync" 18086 8080 "/health" || FAIL=$((FAIL + 1))

if kubectl get svc -n "$NS" cortex-graph >/dev/null 2>&1; then
  if ! PF="$(start_port_forward cortex-graph 18084 8080 /health)"; then
    echo "FAIL graph entity: 000000"
    echo "FAIL graph search: 000000"
    FAIL=$((FAIL + 2))
  else
  ENTITY_CODE="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18084/v1/graph/entities/user:dev || echo "000")"
  SEARCH_CODE="$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:18084/v1/graph/search?q=admin" || echo "000")"
  kill "$PF" >/dev/null 2>&1 || true
  [ "$ENTITY_CODE" = "200" ] && echo "PASS graph entity: ${ENTITY_CODE}" || { echo "FAIL graph entity: ${ENTITY_CODE}"; FAIL=$((FAIL + 1)); }
  [ "$SEARCH_CODE" = "200" ] && echo "PASS graph search: ${SEARCH_CODE}" || { echo "FAIL graph search: ${SEARCH_CODE}"; FAIL=$((FAIL + 1)); }
  fi
fi

if kubectl get svc -n "$NS" cortex-auth >/dev/null 2>&1; then
  if ! PF="$(start_port_forward cortex-auth 18085 8080 /health)"; then
    echo "FAIL auth issue concrete flow: port-forward unavailable"
    FAIL=$((FAIL + 1))
  else
  ISSUE_RESPONSE="$(curl -s -X POST http://127.0.0.1:18085/v1/tokens/issue \
    -H "Content-Type: application/json" \
    -d '{"subject":"user:alice","trust_score":92,"scopes":["read:graph","read:audit"],"device_id":"device-corp-01","session_id":"session-risk4","dpop_thumbprint":"thumb-corp-01","principal_type":"human","mfa_verified":true}' || echo '{}')"
  TOKEN="$(echo "$ISSUE_RESPONSE" | jq -r '.token // empty')"
  if [ -n "$TOKEN" ]; then
    VALIDATE_CODE="$(curl -s -o /tmp/cortex-auth-validate.json -w "%{http_code}" \
      -X POST http://127.0.0.1:18085/v1/tokens/validate \
      -H "Content-Type: application/json" \
      -d "{\"token\":\"${TOKEN}\"}" || echo "000")"
    [ "$VALIDATE_CODE" = "200" ] && echo "PASS auth issue+validate concrete flow: ${VALIDATE_CODE}" || { echo "FAIL auth issue+validate concrete flow: ${VALIDATE_CODE}"; FAIL=$((FAIL + 1)); }
  else
    echo "FAIL auth issue concrete flow: no token returned"
    FAIL=$((FAIL + 1))
  fi
  kill "$PF" >/dev/null 2>&1 || true
  fi
fi

if kubectl get svc -n "$NS" cortex-sync >/dev/null 2>&1; then
  if ! PF="$(start_port_forward cortex-sync 18086 8080 /health)"; then
    echo "FAIL sync delta concrete flow: port-forward unavailable"
    FAIL=$((FAIL + 1))
  else
  JOB_RESPONSE="$(curl -s -X POST http://127.0.0.1:18086/v1/sync/delta \
    -H "Content-Type: application/json" \
    -d '{"source":"ad-prod-eu","dry_run":true}' || echo '{}')"
  JOB_ID="$(echo "$JOB_RESPONSE" | jq -r '.id // empty')"
  if [ -n "$JOB_ID" ]; then
    JOB_CODE="$(curl -s -o /tmp/cortex-sync-job.json -w "%{http_code}" "http://127.0.0.1:18086/v1/sync/jobs/${JOB_ID}" || echo "000")"
    [ "$JOB_CODE" = "200" ] && echo "PASS sync delta job concrete flow: ${JOB_CODE}" || { echo "FAIL sync delta job concrete flow: ${JOB_CODE}"; FAIL=$((FAIL + 1)); }
    kubectl rollout restart deployment/cortex-sync -n "$NS" >/dev/null
    kubectl rollout status deployment/cortex-sync -n "$NS" --timeout=300s >/dev/null
    if PF_AFTER="$(start_port_forward cortex-sync 19086 8080 /health)"; then
      JOB_AFTER_CODE="$(curl -s -o /tmp/cortex-sync-job-after.json -w "%{http_code}" "http://127.0.0.1:19086/v1/sync/jobs/${JOB_ID}" || echo "000")"
      [ "$JOB_AFTER_CODE" = "200" ] && echo "PASS sync persistence after restart: ${JOB_AFTER_CODE}" || { echo "FAIL sync persistence after restart: ${JOB_AFTER_CODE}"; FAIL=$((FAIL + 1)); }
      kill "$PF_AFTER" >/dev/null 2>&1 || true
    else
      echo "FAIL sync persistence after restart: 000000"
      FAIL=$((FAIL + 1))
    fi
  else
    echo "FAIL sync delta concrete flow: no job id returned"
    FAIL=$((FAIL + 1))
  fi
  kill "$PF" >/dev/null 2>&1 || true
  fi
fi

if kubectl get svc -n "$NS" cortex-approval >/dev/null 2>&1; then
  if ! PF="$(start_port_forward cortex-approval 18081 8080 /readyz)"; then
    echo "FAIL approval persistence setup: port-forward unavailable"
    FAIL=$((FAIL + 1))
  else
  APPROVAL_RESPONSE="$(curl -s -X POST http://127.0.0.1:18081/v1/approvals \
    -H "Content-Type: application/json" \
    -d '{"plan_id":"plan-persist","requestor_id":"cortex-obs-agent","actions":[{"taskId":"task-persist","intent":"restart_pod cortex-auth","riskLevel":4,"dryRunRequired":true}],"reasoning":"persist check","risk_level":4}' || echo '{}')"
  APPROVAL_ID="$(echo "$APPROVAL_RESPONSE" | jq -r '.request_id // empty')"
  if [ -n "$APPROVAL_ID" ]; then
    kubectl rollout restart deployment/cortex-approval -n "$NS" >/dev/null
    kubectl rollout status deployment/cortex-approval -n "$NS" --timeout=300s >/dev/null
    if PF_AFTER="$(start_port_forward cortex-approval 19081 8080 /readyz)"; then
      APPROVAL_AFTER_CODE="$(curl -s -o /tmp/cortex-approval-after.json -w "%{http_code}" "http://127.0.0.1:19081/v1/approvals/${APPROVAL_ID}" || echo "000")"
      [ "$APPROVAL_AFTER_CODE" = "200" ] && echo "PASS approval persistence after restart: ${APPROVAL_AFTER_CODE}" || { echo "FAIL approval persistence after restart: ${APPROVAL_AFTER_CODE}"; FAIL=$((FAIL + 1)); }
      kill "$PF_AFTER" >/dev/null 2>&1 || true
    else
      echo "FAIL approval persistence after restart: 000000"
      FAIL=$((FAIL + 1))
    fi
  else
    echo "FAIL approval persistence setup: no request id returned"
    FAIL=$((FAIL + 1))
  fi
  kill "$PF" >/dev/null 2>&1 || true
  fi
fi

if kubectl get svc -n "$NS" cortex-audit >/dev/null 2>&1; then
  if ! PF="$(start_port_forward cortex-audit 18082 8080 /readyz)"; then
    echo "FAIL audit persistence setup: port-forward unavailable"
    FAIL=$((FAIL + 1))
  else
  AUDIT_RESPONSE="$(curl -s -X POST http://127.0.0.1:18082/v1/events \
    -H "Content-Type: application/json" \
    -d '{"principal_id":"cortex-obs-agent","principal_type":"ai_agent","event_type":"obs.autonomous_action","action":"write","decision":"allow","reason":"persist check","risk_level":3,"metadata":{"service":"cortex-auth"}}' || echo '{}')"
  AUDIT_ID="$(echo "$AUDIT_RESPONSE" | jq -r '.event_id // empty')"
  if [ -n "$AUDIT_ID" ]; then
    kubectl rollout restart deployment/cortex-audit -n "$NS" >/dev/null
    kubectl rollout status deployment/cortex-audit -n "$NS" --timeout=300s >/dev/null
    if PF_AFTER="$(start_port_forward cortex-audit 19082 8080 /readyz)"; then
      AUDIT_AFTER_CODE="$(curl -s -o /tmp/cortex-audit-after.json -w "%{http_code}" "http://127.0.0.1:19082/v1/events/${AUDIT_ID}" || echo "000")"
      [ "$AUDIT_AFTER_CODE" = "200" ] && echo "PASS audit persistence after restart: ${AUDIT_AFTER_CODE}" || { echo "FAIL audit persistence after restart: ${AUDIT_AFTER_CODE}"; FAIL=$((FAIL + 1)); }
      kill "$PF_AFTER" >/dev/null 2>&1 || true
    else
      echo "FAIL audit persistence after restart: 000000"
      FAIL=$((FAIL + 1))
    fi
  else
    echo "FAIL audit persistence setup: no event id returned"
    FAIL=$((FAIL + 1))
  fi
  kill "$PF" >/dev/null 2>&1 || true
  fi
fi

if [ "$FAIL" -eq 0 ]; then
  echo "RUNTIME API VALIDATION: PASSED"
  exit 0
fi

echo "RUNTIME API VALIDATION: FAILED (${FAIL})"
exit 1
