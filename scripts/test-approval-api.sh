#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker build -t cortex/cortex-approval:test services/cortex-approval >/tmp/cortex-approval-docker-build.log 2>&1
docker run --rm cortex/cortex-approval:test python -m pytest -q /app/tests

bash scripts/setup-observability.sh
bash scripts/setup-console.sh

kubectl port-forward -n cortex-system svc/cortex-approval 18081:8080 >/tmp/cortex-approval-pf.log 2>&1 &
PF=$!

cleanup() {
  kill "$PF" 2>/dev/null || true
}
trap cleanup EXIT

sleep 5

created="$(curl -s -X POST http://127.0.0.1:18081/v1/approvals \
  -H "Content-Type: application/json" \
  -d '{"plan_id":"plan-api","requestor_id":"cortex-obs-agent","actions":[{"taskId":"task-1","intent":"restart_pod cortex-auth","riskLevel":5,"dryRunRequired":true}],"reasoning":"API coverage test","risk_level":5}')"
echo "created=$created"

request_id="$(echo "$created" | jq -r '.request_id')"
echo "request_id=$request_id"
echo "get=$(curl -s "http://127.0.0.1:18081/v1/approvals/${request_id}")"
echo "pending=$(curl -s "http://127.0.0.1:18081/v1/approvals?status=pending" | jq length)"
echo "first_approve=$(curl -s -X POST "http://127.0.0.1:18081/v1/approvals/${request_id}/approve" -H "Content-Type: application/json" -d '{"comment":"first"}')"
echo "second_approve=$(curl -s -X POST "http://127.0.0.1:18081/v1/approvals/${request_id}/approve" -H "Content-Type: application/json" -d '{"comment":"second"}')"
echo "approved=$(curl -s "http://127.0.0.1:18081/v1/approvals?status=approved" | jq length)"
