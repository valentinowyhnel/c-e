#!/bin/bash
set -euo pipefail

echo "=== Setup enforcement Cortex Phase 3 ==="

docker build -t cortex/cortex-auth:dev services/cortex-auth
docker build -t cortex/cortex-sync:dev services/cortex-sync
docker build -t cortex/cortex-gateway:dev services/cortex-gateway
docker build -t cortex/cortex-graph:dev services/cortex-graph

kind load docker-image cortex/cortex-auth:dev --name cortex-dev
kind load docker-image cortex/cortex-sync:dev --name cortex-dev
kind load docker-image cortex/cortex-gateway:dev --name cortex-dev
kind load docker-image cortex/cortex-graph:dev --name cortex-dev

helm upgrade --install cortex-infra helm/cortex-infra \
  --namespace cortex-system \
  --create-namespace \
  --wait --timeout=600s

helm upgrade --install cortex-enforcement helm/cortex-enforcement \
  --namespace cortex-system \
  --create-namespace \
  --timeout=600s

kubectl rollout status statefulset/cortex-postgres -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-auth -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-sync -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-gateway -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-graph -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-opa -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-envoy -n cortex-system --timeout=300s
kubectl rollout status statefulset/cortex-neo4j -n cortex-system --timeout=600s

echo "Enforcement stack deploye: auth, sync, gateway, graph, OPA, Envoy, Neo4j."
