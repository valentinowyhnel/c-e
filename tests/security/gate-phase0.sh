#!/bin/bash
set -euo pipefail

PASS=0
FAIL=0

pass() { echo "  PASS - $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }

echo ""
echo "CORTEX GATE PHASE 0"
echo ""

command -v docker >/dev/null 2>&1 && pass "docker" || fail "docker manquant"
command -v kind >/dev/null 2>&1 && pass "kind" || fail "kind manquant"
command -v kubectl >/dev/null 2>&1 && pass "kubectl" || fail "kubectl manquant"
command -v helm >/dev/null 2>&1 && pass "helm" || fail "helm manquant"
command -v terraform >/dev/null 2>&1 && pass "terraform" || fail "terraform manquant"
command -v vault >/dev/null 2>&1 && pass "vault CLI" || fail "vault CLI manquant"
command -v jq >/dev/null 2>&1 && pass "jq" || fail "jq manquant"
command -v opa >/dev/null 2>&1 && pass "opa" || fail "opa manquant"
command -v go >/dev/null 2>&1 && pass "go" || fail "go manquant"
command -v uv >/dev/null 2>&1 && pass "uv" || fail "uv manquant"
command -v k9s >/dev/null 2>&1 && pass "k9s" || fail "k9s manquant"

if command -v free >/dev/null 2>&1; then
  AVAIL=$(free -m | awk '/^Mem:/ {print $7}')
  [ "${AVAIL:-0}" -gt 3000 ] && pass "RAM disponible (${AVAIL}Mi)" || fail "RAM insuffisante"
else
  fail "commande free indisponible"
fi

[ -f "Makefile" ] && pass "Makefile present" || fail "Makefile absent"
[ -d "services" ] && pass "Dossier services/" || fail "Dossier services/ absent"
[ -d "helm" ] && pass "Dossier helm/" || fail "Dossier helm/ absent"
[ -d "policies" ] && pass "Dossier policies/" || fail "Dossier policies/ absent"
[ -d "proto" ] && pass "Dossier proto/" || fail "Dossier proto/ absent"

echo ""
printf "PASS: %d  FAIL: %d\n" "$PASS" "$FAIL"

if [ "$FAIL" -eq 0 ]; then
  echo "GATE PHASE 0 : PASSED"
  exit 0
fi

echo "GATE PHASE 0 : FAILED"
exit 1
