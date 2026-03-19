#!/bin/bash
set -euo pipefail

echo "=== Setup identite Cortex Phase 2 ==="

helm upgrade --install cortex-identity helm/cortex-identity \
  --namespace cortex-system \
  --create-namespace \
  --wait --timeout=600s

kubectl rollout status deployment/keycloak -n cortex-system --timeout=600s
kubectl rollout status deployment/lldap -n cortex-system --timeout=300s
kubectl rollout status statefulset/cortex-valkey -n cortex-system --timeout=300s

echo "Identity stack deploye: Keycloak, Lldap, Valkey."
