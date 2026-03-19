#!/bin/bash
set -euo pipefail

echo "=== Setup Vault dans Kind ==="

helm repo add hashicorp https://helm.releases.hashicorp.com --force-update
helm upgrade --install vault hashicorp/vault \
  --namespace vault-system \
  --create-namespace \
  --set "server.dev.enabled=true" \
  --set "server.dev.devRootToken=cortex-root-token-CHANGE-IN-PROD" \
  --set "injector.enabled=false" \
  --set "server.resources.requests.memory=256Mi" \
  --set "server.resources.limits.memory=512Mi" \
  --wait --timeout=240s

kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=vault \
  -n vault-system --timeout=120s

kubectl patch serviceaccount vault -n vault-system -p '{"automountServiceAccountToken": true}'

if ! kubectl get secret -n vault-system vault-token >/dev/null 2>&1; then
  kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: vault-token
  namespace: vault-system
  annotations:
    kubernetes.io/service-account.name: vault
type: kubernetes.io/service-account-token
EOF
fi

kubectl wait --for=jsonpath='{.data.token}' secret/vault-token -n vault-system --timeout=120s

kubectl port-forward -n vault-system svc/vault 8200:8200 >/tmp/cortex-vault-port-forward.log 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT
sleep 5

export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='cortex-root-token-CHANGE-IN-PROD'

vault status >/dev/null
vault secrets list -format=json | jq -e 'has("secret/")' >/dev/null || vault secrets enable -path=secret kv-v2

if ! vault auth list -format=json | jq -e 'has("kubernetes/")' >/dev/null; then
  vault auth enable kubernetes
fi

KUBE_HOST=$(kubectl config view --raw -o jsonpath='{.clusters[0].cluster.server}')
KUBE_CA_CERT=$(kubectl config view --raw --minify --flatten -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d)
TOKEN_REVIEW_JWT=$(kubectl get secret vault-token -n vault-system -o jsonpath='{.data.token}' | base64 -d)

vault write auth/kubernetes/config \
  kubernetes_host="${KUBE_HOST}" \
  kubernetes_ca_cert="${KUBE_CA_CERT}" \
  token_reviewer_jwt="${TOKEN_REVIEW_JWT}"

SERVICES=(
  "cortex-auth:secret/data/cortex/auth/*"
  "cortex-policy:secret/data/cortex/policy/*"
  "cortex-graph:secret/data/cortex/graph/*"
  "cortex-gateway:secret/data/cortex/gateway/*"
  "cortex-sync:secret/data/cortex/sync/*"
  "cortex-trust-engine:secret/data/cortex/trust-engine/*"
  "cortex-mcp-server:secret/data/cortex/mcp/*"
  "cortex-orchestrator:secret/data/cortex/orchestrator/*"
  "cortex-agents:secret/data/cortex/agents/*"
  "cortex-sentinel:secret/data/cortex/sentinel/*"
  "cortex-vllm:secret/data/cortex/vllm/*"
  "cortex-approval:secret/data/cortex/approval/*"
  "cortex-console:secret/data/cortex/console/*"
)

for entry in "${SERVICES[@]}"; do
  SVC="${entry%%:*}"
  SECRET_PATH="${entry##*:}"

  vault policy write "$SVC" - <<EOF
path "$SECRET_PATH" { capabilities = ["read"] }
path "secret/metadata/cortex/${SVC#cortex-}/*" { capabilities = ["list"] }
EOF

  vault write "auth/kubernetes/role/$SVC" \
    bound_service_account_names="$SVC" \
    bound_service_account_namespaces="cortex-system" \
    policies="$SVC" \
    ttl="1h"
done

vault kv put secret/cortex/graph/config \
  neo4j_uri="bolt://cortex-neo4j:7687" \
  neo4j_database="cortex" \
  neo4j_password="CHANGE-IN-PROD"

vault kv put secret/cortex/trust-engine/config \
  redis_url="redis://:CHANGE-IN-PROD@cortex-valkey:6379" \
  anomaly_threshold="0.7"

vault kv put secret/cortex/mcp/config \
  anthropic_api_key="REMPLACER-PAR-CLE-ANTHROPIC" \
  sentinel_url="http://cortex-sentinel:8080"

vault kv put secret/cortex/console/config \
  nextauth_secret="CHANGE-IN-PROD-32-chars-minimum" \
  keycloak_client_secret="CHANGE-IN-PROD"

echo "Vault deploye et configure pour l'auth Kubernetes."
