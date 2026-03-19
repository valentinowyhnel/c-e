#!/bin/bash
set -euo pipefail

echo "=== Registration entries SPIRE ==="

SERVER_POD=$(kubectl get pod -n spire-system -l app=spire-server -o jsonpath='{.items[0].metadata.name}')

register_entry() {
  kubectl exec -n spire-system "$SERVER_POD" -- /opt/spire/bin/spire-server entry create \
    -spiffeID "$1" \
    -parentID spiffe://cortex.local/ns/spire-system/sa/spire-agent \
    -selector "$2" \
    -selector "$3" \
    >/dev/null
}

register_entry "spiffe://cortex.local/ns/cortex-system/sa/cortex-auth" "k8s:ns:cortex-system" "k8s:sa:cortex-auth"
register_entry "spiffe://cortex.local/ns/cortex-system/sa/cortex-policy" "k8s:ns:cortex-system" "k8s:sa:cortex-policy"
register_entry "spiffe://cortex.local/ns/cortex-system/sa/cortex-gateway" "k8s:ns:cortex-system" "k8s:sa:cortex-gateway"
register_entry "spiffe://cortex.local/ns/cortex-system/sa/cortex-trust-engine" "k8s:ns:cortex-system" "k8s:sa:cortex-trust-engine"
register_entry "spiffe://cortex.local/ns/cortex-system/sa/cortex-sentinel-machine" "k8s:ns:cortex-system" "k8s:sa:cortex-sentinel-machine"

echo "Registration entries minimales appliquees."
