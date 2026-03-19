#!/bin/bash
set -euo pipefail

PASS=0; FAIL=0; WARN=0
pass() { echo "    $1"; ((PASS++)) || true; }
fail() { echo "    $1"; ((FAIL++)) || true; }
warn() { echo "  ~  $1"; ((WARN++)) || true; }

echo ""
echo "   CORTEX GATE MCP v2"
echo ""

kubectl get deploy -n cortex-system cortex-mcp-server >/dev/null 2>&1 && pass "MCP deployment present" || fail "MCP deployment absent"

if kubectl get svc -n cortex-system cortex-mcp-server >/dev/null 2>&1; then
  kubectl port-forward -n cortex-system svc/cortex-mcp-server 18080:8080 >/tmp/cortex-mcp-gate.log 2>&1 &
  PF=$!
  sleep 5

  HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18080/healthz || echo "000")
  [ "$HEALTH" = "200" ] && pass "MCP /healthz OK" || fail "MCP /healthz: $HEALTH"

  READY=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18080/readyz || echo "000")
  if [ "$READY" = "200" ]; then
    pass "MCP /readyz OK"
  else
    warn "MCP /readyz: $READY"
  fi

  DEBUG=$(curl -s -X POST http://127.0.0.1:18080/mcp/debug/route \
    -H "Content-Type: application/json" \
    -d '{"task":"generate rego policy for admin access","input":"restrict admin to mfa users"}')
  MODEL=$(echo "$DEBUG" | jq -r '.model_id // empty')
  SOURCE=$(echo "$DEBUG" | jq -r '.routing_source // empty')
  [ "$MODEL" = "codellama-13b" ] && pass "debug route returns codellama-13b" || warn "debug route model=$MODEL"
  [ -n "$SOURCE" ] && pass "debug route exposes routing source ($SOURCE)" || fail "routing source absent"

  METRICS=$(curl -s http://127.0.0.1:18080/metrics || true)
  echo "$METRICS" | grep -q "cortex_mcp_calls_total" && pass "metrics include calls_total" || fail "metrics missing calls_total"
  echo "$METRICS" | grep -q "cortex_mcp_call_duration_seconds" && pass "metrics include duration" || warn "metrics missing duration"

  BATCH=$(curl -s -X POST http://127.0.0.1:18080/mcp/complete \
    -H "Content-Type: application/json" \
    -d '{"task":"batch classify","input":"","batch":{"batch_id":"test-batch-001","requests":[{"tool":"read_graph","params":{"entity_id":"user:alice"}},{"tool":"read_graph","params":{"entity_id":"user:bob"}}],"parallel":2}}')
  BATCH_ID=$(echo "$BATCH" | jq -r '.batch_id // empty')
  [ -n "$BATCH_ID" ] && pass "batch mode operational" || fail "batch mode failed"

  DRY=$(curl -s -X POST http://127.0.0.1:18080/mcp/complete \
    -H "Content-Type: application/json" \
    -d '{"task":"revoke sessions","input":"revoke all sessions for user:alice","tool":"revoke_user_sessions","tool_params":{"user_id":"user:alice-test"},"dry_run":true}')
  DRY_OK=$(echo "$DRY" | jq -r '.dry_run_result.would_succeed // empty')
  [ -n "$DRY_OK" ] && pass "dry-run mode operational" || fail "dry-run mode failed"

  TURN=$(curl -s -X POST http://127.0.0.1:18080/mcp/complete \
    -H "Content-Type: application/json" \
    -d '{"task":"investigate incident","input":"What happened to user alice in the last hour?","session_id":"test-session-gate-001"}')
  SESSION_ID=$(echo "$TURN" | jq -r '.session_id // empty')
  [ "$SESSION_ID" = "test-session-gate-001" ] && pass "multi-turn session preserved" || warn "multi-turn session missing"

  kill "$PF" >/dev/null 2>&1 || true
else
  fail "MCP service absent"
fi

for dep in cortex-orchestrator cortex-sentinel cortex-vllm; do
  kubectl get deploy -n cortex-system "$dep" >/dev/null 2>&1 && pass "$dep deployed" || warn "$dep absent"
done

echo ""
printf "  PASS: %d  FAIL: %d  WARN: %d\n" "$PASS" "$FAIL" "$WARN"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
