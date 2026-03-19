#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

python3 - "${ROOT_DIR}" "${REPORT_DIR}/ext-authz.json" "${EXT_AUTHZ_P99_MAX_MS:-250}" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
report = pathlib.Path(sys.argv[2])
max_timeout_ms = float(sys.argv[3])
text = (root / "helm/cortex-enforcement/templates/envoy-configmap.yaml").read_text(encoding="utf-8")

errors = []
warnings = []

if "envoy.filters.http.ext_authz" not in text:
    errors.append("ext_authz filter missing")

if "failure_mode_allow: true" in text:
    errors.append("ext_authz explicitly allows failure")

timeout_match = re.search(r"timeout:\s*([0-9.]+)s", text)
if not timeout_match:
    errors.append("ext_authz timeout missing")
    timeout_ms = None
else:
    timeout_ms = float(timeout_match.group(1)) * 1000.0
    if timeout_ms > max_timeout_ms:
        errors.append(f"ext_authz timeout {timeout_ms:.0f}ms exceeds {max_timeout_ms:.0f}ms")

status = "passed" if not errors else "failed"
report.write_text(json.dumps({"status": status, "timeout_ms": timeout_ms, "warnings": warnings, "errors": errors}, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)
PY

