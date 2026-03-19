#!/bin/bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-cortex-system}"
APP_LABEL="${APP_LABEL:-app.kubernetes.io/name=cortex-sentinel-machine}"
SERVICE_NAME="${SERVICE_NAME:-cortex-sentinel-machine}"
EXPECTED_SPIFFE_SA="${EXPECTED_SPIFFE_SA:-cortex-sentinel-machine}"

echo "=== Sentinel Machine validation ==="

echo "[1/8] DaemonSet status"
kubectl get daemonset cortex-sentinel-machine -n "$NAMESPACE" -o wide
kubectl rollout status daemonset/cortex-sentinel-machine -n "$NAMESPACE" --timeout=300s

echo "[2/8] Pods"
kubectl get pods -n "$NAMESPACE" -l "$APP_LABEL" -o wide

echo "[3/8] Service"
kubectl get service "$SERVICE_NAME" -n "$NAMESPACE" -o wide

echo "[4/8] Recent logs"
POD_NAME="$(kubectl get pod -n "$NAMESPACE" -l "$APP_LABEL" -o jsonpath='{.items[0].metadata.name}')"
kubectl logs -n "$NAMESPACE" "$POD_NAME" --tail=120

echo "[5/8] Environment wiring"
kubectl exec -n "$NAMESPACE" "$POD_NAME" -- sh -lc 'printenv | grep -E "NATS_URL|SENTINEL_CORTEX_|SENTINEL_ENABLE_NATS_BUS|SENTINEL_GRPC_|SENTINEL_OBSERVABILITY_" | sort'

echo "[6/8] Observability health"
TOKEN="$(kubectl exec -n "$NAMESPACE" "$POD_NAME" -- sh -lc 'printenv SENTINEL_OBSERVABILITY_TOKEN')"
kubectl exec -n "$NAMESPACE" "$POD_NAME" -- sh -lc "wget -qO- --header='Authorization: Bearer ${TOKEN}' http://127.0.0.1:18080/health"

echo "[7/8] Local queue and state"
kubectl exec -n "$NAMESPACE" "$POD_NAME" -- sh -lc 'ls -la /var/lib/cortex/sentinel-machine || true'

echo "[8/8] SPIFFE alignment hint"
echo "Expected service account for SPIRE entry: ${EXPECTED_SPIFFE_SA}"
kubectl get serviceaccount "$EXPECTED_SPIFFE_SA" -n "$NAMESPACE" -o yaml

echo "Sentinel Machine validation completed."

