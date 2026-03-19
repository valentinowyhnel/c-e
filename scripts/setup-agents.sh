#!/bin/bash
set -euo pipefail

echo "=== Setup agents Cortex Phase 4 ==="

docker build -t cortex/cortex-vllm:dev services/cortex-vllm
docker build -t cortex/cortex-sentinel:dev services/cortex-sentinel
docker build -t cortex/cortex-sentinel-machine:dev services/python/cortex-sentinel-machine
docker build -t cortex/cortex-mcp-server:dev services/cortex-mcp-server
docker build -t cortex/cortex-orchestrator:dev services/cortex-orchestrator

kind load docker-image cortex/cortex-vllm:dev --name cortex-dev
kind load docker-image cortex/cortex-sentinel:dev --name cortex-dev
kind load docker-image cortex/cortex-sentinel-machine:dev --name cortex-dev
kind load docker-image cortex/cortex-mcp-server:dev --name cortex-dev
kind load docker-image cortex/cortex-orchestrator:dev --name cortex-dev

helm upgrade --install cortex-agents helm/cortex-agents \
  --namespace cortex-system \
  --create-namespace \
  --timeout=600s

helm upgrade --install cortex-sentinel-machine helm/cortex-sentinel-machine \
  --namespace cortex-system \
  --create-namespace \
  --timeout=600s

kubectl rollout status statefulset/cortex-nats -n cortex-system --timeout=600s
kubectl rollout status deployment/cortex-vllm -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-sentinel -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-mcp-server -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-orchestrator -n cortex-system --timeout=300s
kubectl rollout status daemonset/cortex-sentinel-machine -n cortex-system --timeout=300s

echo "Agents platform deploye: NATS, vLLM, Sentinel, Sentinel Machine, MCP server, Orchestrator."
