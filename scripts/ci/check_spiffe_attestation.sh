#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

python3 - "${ROOT_DIR}" "${REPORT_DIR}/spiffe-attestation.json" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
report = pathlib.Path(sys.argv[2])

register = root / "scripts/register-spire-entries.sh"
sentinel_chart = root / "helm/cortex-sentinel-machine/templates/daemonset.yaml"
spire_chart = root / "helm/cortex-spire/templates/agent-daemonset.yaml"

required_ids = {
    "spiffe://cortex.local/ns/cortex-system/sa/cortex-auth",
    "spiffe://cortex.local/ns/cortex-system/sa/cortex-gateway",
    "spiffe://cortex.local/ns/cortex-system/sa/cortex-trust-engine",
    "spiffe://cortex.local/ns/cortex-system/sa/cortex-sentinel-machine",
}

errors = []
register_text = register.read_text(encoding="utf-8")
for spiffe_id in sorted(required_ids):
    if spiffe_id not in register_text:
        errors.append(f"missing registration entry for {spiffe_id}")

sentinel_text = sentinel_chart.read_text(encoding="utf-8")
if "serviceAccountName: {{ .Values.serviceAccount.name }}" not in sentinel_text and "serviceAccountName: cortex-sentinel-machine" not in sentinel_text:
    errors.append("sentinel machine daemonset missing serviceAccountName")

spire_text = spire_chart.read_text(encoding="utf-8")
if "spire-agent" not in spire_text or "agent.sock" not in spire_text:
    errors.append("spire agent daemonset missing socket wiring")

status = "passed" if not errors else "failed"
report.write_text(json.dumps({"status": status, "errors": errors}, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)
PY

