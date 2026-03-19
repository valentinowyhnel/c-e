#!/bin/bash
set -euo pipefail

echo "=== Setup SPIRE dans Kind ==="

kubectl create namespace spire-system --dry-run=client -o yaml | kubectl apply -f -
kubectl label namespace spire-system cortex/tier=identity --overwrite

helm upgrade --install cortex-spire helm/cortex-spire \
  --namespace spire-system \
  --create-namespace \
  --wait --timeout=180s

kubectl wait --for=condition=ready pod -l app=spire-server -n spire-system --timeout=180s
kubectl wait --for=condition=ready pod -l app=spire-agent -n spire-system --timeout=180s

bash scripts/register-spire-entries.sh

echo "SPIRE deploye et registration entries appliquees."
