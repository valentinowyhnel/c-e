#!/bin/bash
set -euo pipefail

echo "=== Setup agents Cortex Phase 4 ==="

SKIP_VLLM="${SKIP_VLLM:-0}"
AGENTS_HELM_ARGS=()

if [ "$SKIP_VLLM" != "1" ]; then
  docker build -t cortex/cortex-vllm:dev services/cortex-vllm
fi
docker build -t cortex/cortex-sentinel:dev services/cortex-sentinel
docker build -t cortex/cortex-sentinel-machine:dev services/python/cortex-sentinel-machine
docker build -t cortex/cortex-mcp-server:dev services/cortex-mcp-server
docker build -t cortex/cortex-orchestrator:dev services/cortex-orchestrator

if [ "$SKIP_VLLM" != "1" ]; then
  kind load docker-image cortex/cortex-vllm:dev --name cortex-dev
else
  AGENTS_HELM_ARGS+=(--set vllm.enabled=false)
fi
kind load docker-image cortex/cortex-sentinel:dev --name cortex-dev
kind load docker-image cortex/cortex-sentinel-machine:dev --name cortex-dev
kind load docker-image cortex/cortex-mcp-server:dev --name cortex-dev
kind load docker-image cortex/cortex-orchestrator:dev --name cortex-dev

helm upgrade --install cortex-agents helm/cortex-agents \
  --namespace cortex-system \
  --create-namespace \
  "${AGENTS_HELM_ARGS[@]}" \
  --timeout=600s

helm upgrade --install cortex-sentinel-machine helm/cortex-sentinel-machine \
  --namespace cortex-system \
  --create-namespace \
  --timeout=600s

kubectl rollout status statefulset/cortex-nats -n cortex-system --timeout=600s
if [ "$SKIP_VLLM" != "1" ]; then
  kubectl rollout status deployment/cortex-vllm -n cortex-system --timeout=300s
fi
kubectl rollout status deployment/cortex-sentinel -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-mcp-server -n cortex-system --timeout=300s
kubectl rollout status deployment/cortex-orchestrator -n cortex-system --timeout=300s
kubectl rollout status daemonset/cortex-sentinel-machine -n cortex-system --timeout=300s

if [ "$SKIP_VLLM" != "1" ]; then
  echo "Agents platform deploye: NATS, vLLM, Sentinel, Sentinel Machine, MCP server, Orchestrator."
else
  echo "Agents platform deploye: NATS, Sentinel, Sentinel Machine, MCP server, Orchestrator. vLLM desactive."
fi
