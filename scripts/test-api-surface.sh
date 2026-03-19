#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker build -t cortex/cortex-approval:test services/cortex-approval >/tmp/cortex-approval-docker-build.log 2>&1
docker run --rm cortex/cortex-approval:test python -m pytest -q /app/tests

docker build -t cortex/cortex-audit:test services/cortex-audit >/tmp/cortex-audit-docker-build.log 2>&1
docker run --rm cortex/cortex-audit:test python -m pytest -q /app/tests

bash scripts/setup-observability.sh
bash scripts/setup-console.sh

kubectl port-forward -n cortex-system svc/cortex-console 3000:3000 >/tmp/cortex-console-pf.log 2>&1 &
PF1=$!
kubectl port-forward -n cortex-system svc/cortex-audit 18082:8080 >/tmp/cortex-audit-pf.log 2>&1 &
PF2=$!
kubectl port-forward -n cortex-system svc/cortex-approval 18081:8080 >/tmp/cortex-approval-pf.log 2>&1 &
PF3=$!

cleanup() {
  kill "$PF1" "$PF2" "$PF3" 2>/dev/null || true
}
trap cleanup EXIT

sleep 8

audit_event="$(curl -s -X POST http://127.0.0.1:18082/v1/events \
  -H "Content-Type: application/json" \
  -d '{"principal_id":"cortex-obs-agent","principal_type":"ai_agent","event_type":"obs.autonomous_action","action":"write","decision":"deny","reason":"smoke audit event","risk_level":4,"metadata":{"service":"cortex-auth"}}')"
echo "audit_event=$audit_event"

approval="$(curl -s -X POST http://127.0.0.1:18081/v1/approvals \
  -H "Content-Type: application/json" \
  -d '{"plan_id":"plan-surface","requestor_id":"cortex-obs-agent","actions":[{"taskId":"task-surface","intent":"restart_pod cortex-auth","riskLevel":4,"dryRunRequired":true}],"reasoning":"surface test","risk_level":4}')"
echo "approval=$approval"
approval_id="$(echo "$approval" | jq -r '.request_id')"

echo "console_health=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/api/health)"
echo "dashboard=$(curl -s http://127.0.0.1:3000/api/dashboard)"
echo "events=$(curl -s http://127.0.0.1:3000/api/events)"
echo "graph=$(curl -s http://127.0.0.1:3000/api/graph/overview)"
echo "approvals_pending=$(curl -s http://127.0.0.1:3000/api/approvals?status=pending)"
echo "approval_detail=$(curl -s http://127.0.0.1:3000/api/approvals/${approval_id})"
