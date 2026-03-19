#!/bin/bash
set -euo pipefail

echo "=== Setup cluster Kind Cortex ==="

if ! kind get clusters | grep -qx "cortex-dev"; then
  kind create cluster --config infra/local/kind-cluster.yaml
else
  echo "Cluster cortex-dev deja present."
fi

kubectl cluster-info >/dev/null
kubectl wait --for=condition=Ready node --all --timeout=180s

echo "=== Installation Calico ==="
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.27.3/manifests/calico.yaml
kubectl rollout status daemonset/calico-node -n kube-system --timeout=300s
kubectl rollout status deployment/calico-kube-controllers -n kube-system --timeout=300s

echo "=== Namespaces Cortex ==="
kubectl create namespace cortex-system --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace vault-system --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace spire-system --dry-run=client -o yaml | kubectl apply -f -
kubectl label namespace cortex-system cortex/tier=control-plane --overwrite
kubectl label namespace vault-system cortex/tier=secrets --overwrite
kubectl label namespace spire-system cortex/tier=identity --overwrite

echo "=== NetworkPolicies deny-all ==="
helm upgrade --install cortex-infra helm/cortex-infra \
  --namespace cortex-system \
  --create-namespace \
  --wait --timeout=120s

echo "Cluster initialise avec Calico, namespaces et deny-all."
