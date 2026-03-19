#!/bin/bash
set -e
echo "=== Setup Système Immunitaire v2 ==="

kubectl port-forward -n vault-system svc/vault 8200:8200 &>/dev/null &
PF=$!
sleep 2
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=cortex-root-token-CHANGE-IN-PROD

AUDIT_IP=$(kubectl get svc cortex-audit -n cortex-system -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "")

vault kv put secret/cortex/sentinel/config \
  nats_url="nats://cortex-nats:4222" \
  trust_engine_url="http://cortex-trust-engine:8080" \
  audit_ip="${AUDIT_IP}"

vault policy write cortex-sentinel - <<'EOF'
path "secret/data/cortex/sentinel/*" { capabilities = ["read"] }
EOF

vault write auth/kubernetes/role/cortex-sentinel \
  bound_service_account_names=cortex-sentinel \
  bound_service_account_namespaces=cortex-system \
  policies=cortex-sentinel \
  ttl=1h

kill $PF 2>/dev/null || true
echo "Vault OK"

cat > /tmp/cortex_falco_rules.yaml <<'RULES'
- rule: Suspicious Process Execution
  desc: Process suspect dans le périmètre Cortex
  condition: >
    spawned_process and
    proc.name in (nmap, masscan, hydra, netcat, nc, mimikatz, john, hashcat)
  output: "Suspicious process %proc.name (user=%user.name cmdline=%proc.cmdline)"
  priority: WARNING
  tags: [cortex, process]

- rule: Credential Dump Attempt
  desc: Tentative de dump credentials
  condition: >
    spawned_process and
    (proc.cmdline contains "lsass" or proc.cmdline contains "procdump")
  output: "Credential dump (cmdline=%proc.cmdline user=%user.name)"
  priority: CRITICAL
  tags: [cortex, credentials, hard_stop]

- rule: Security Tool Killed
  desc: Outil Cortex tué
  condition: >
    evt.type = kill and
    proc.name in (cortex-sentinel, falco, auditd)
  output: "Security tool killed (%proc.name by %user.name)"
  priority: CRITICAL
  tags: [cortex, tamper, hard_stop]

- rule: Sensitive Secret Access
  desc: Accès secrets sensibles
  condition: >
    open_read and
    (fd.name contains "/vault/secrets" or fd.name contains "/.ssh/")
  output: "Sensitive file %fd.name accessed by %proc.name"
  priority: HIGH
  tags: [cortex, secrets]
RULES

kubectl create configmap cortex-falco-rules \
  --from-file=cortex_rules.yaml=/tmp/cortex_falco_rules.yaml \
  -n cortex-system --dry-run=client -o yaml | kubectl apply -f -
echo "Falco rules OK"
echo "=== Setup terminé ==="
