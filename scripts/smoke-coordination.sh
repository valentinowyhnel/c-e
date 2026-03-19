#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

kubectl get pods -n cortex-system | grep -E "cortex-(console|approval|obs-agent|nats-bridge)|opentelemetry-collector"

kubectl port-forward -n cortex-system svc/cortex-console 3000:3000 >/tmp/cortex-console-pf.log 2>&1 &
PF1=$!
kubectl port-forward -n cortex-system svc/cortex-approval 18081:8080 >/tmp/cortex-approval-pf.log 2>&1 &
PF2=$!
kubectl port-forward -n cortex-system svc/cortex-obs-agent 18090:8080 >/tmp/cortex-obs-pf.log 2>&1 &
PF3=$!

cleanup() {
  kill "$PF1" "$PF2" "$PF3" 2>/dev/null || true
}
trap cleanup EXIT

sleep 8

echo "console_root=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/)"
echo "console_health=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/api/health)"

created="$(curl -s -X POST http://127.0.0.1:18081/v1/approvals \
  -H "Content-Type: application/json" \
  -d '{"plan_id":"plan-live","requestor_id":"cortex-obs-agent","actions":[{"taskId":"task-live","intent":"restart_pod cortex-auth","riskLevel":4,"dryRunRequired":true}],"reasoning":"Live coordination test","risk_level":4}')"
echo "created=$created"

request_id="$(echo "$created" | jq -r '.request_id')"
echo "request_id=$request_id"

echo "approvals_api=$(curl -s http://127.0.0.1:3000/api/approvals | jq length)"
echo "approvals_first=$(curl -s http://127.0.0.1:3000/api/approvals | jq -r '.[0].requestId')"

approve_status="$(curl -s -o /tmp/approve.json -w "%{http_code}" \
  -X POST "http://127.0.0.1:3000/api/approvals/${request_id}/approve" \
  -H "Content-Type: application/json" \
  -d '{"comment":"approved in smoke test"}')"
echo "approve_status=$approve_status"
echo "approve_body=$(cat /tmp/approve.json)"
echo "approvals_after=$(curl -s http://127.0.0.1:3000/api/approvals | jq length)"
echo "obs_health=$(curl -s http://127.0.0.1:18090/healthz)"
