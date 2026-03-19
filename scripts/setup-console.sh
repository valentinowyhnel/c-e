#!/bin/bash
set -euo pipefail

echo "=== Setup console Cortex Phase 5 ==="

docker build -t cortex/cortex-console:dev services/cortex-console
kind load docker-image cortex/cortex-console:dev --name cortex-dev

helm upgrade --install cortex-console helm/cortex-console \
  --namespace cortex-system \
  --create-namespace \
  --timeout=600s

kubectl rollout restart deployment/cortex-console -n cortex-system
kubectl rollout status deployment/cortex-console -n cortex-system --timeout=600s

echo "Console SOC deployee."
