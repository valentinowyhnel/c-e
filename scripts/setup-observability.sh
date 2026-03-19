#!/bin/bash
set -euo pipefail

echo "=== Setup observability Cortex Phase 6 ==="

docker build -t cortex/cortex-nats-bridge:dev services/cortex-nats-bridge
docker build -t cortex/cortex-obs-agent:dev services/cortex-obs-agent
docker build -t cortex/cortex-audit:dev services/cortex-audit
docker build -t cortex/cortex-approval:dev services/cortex-approval
docker build -t cortex/cortex-gateway:dev services/cortex-gateway

kind load docker-image cortex/cortex-nats-bridge:dev --name cortex-dev
kind load docker-image cortex/cortex-obs-agent:dev --name cortex-dev
kind load docker-image cortex/cortex-audit:dev --name cortex-dev
kind load docker-image cortex/cortex-approval:dev --name cortex-dev
kind load docker-image cortex/cortex-gateway:dev --name cortex-dev

helm upgrade --install cortex-infra helm/cortex-infra \
  --namespace cortex-system \
  --create-namespace \
  --wait --timeout=600s

helm upgrade --install cortex-observability helm/cortex-observability \
  --namespace cortex-system \
  --create-namespace \
  --wait --timeout=600s

kubectl rollout restart deployment/cortex-gateway -n cortex-system
kubectl rollout restart deployment/cortex-nats-bridge -n cortex-system
kubectl rollout restart deployment/cortex-obs-agent -n cortex-system
kubectl rollout restart deployment/cortex-audit -n cortex-system
kubectl rollout restart deployment/cortex-approval -n cortex-system
kubectl rollout restart deployment/opentelemetry-collector -n cortex-system
kubectl rollout status statefulset/cortex-postgres -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-gateway -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-nats-bridge -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-obs-agent -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-audit -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-approval -n cortex-system --timeout=300s
kubectl rollout status deployment/opentelemetry-collector -n cortex-system --timeout=300s

echo "Observabilite agentique deployee."
