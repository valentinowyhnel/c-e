#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

python3 - "${ARTIFACT_DIR}/reports/post-deploy-prod.json" "${REPORT_DIR}/canary-health.json" "${EXT_AUTHZ_P99_MAX_MS:-250}" "${TRUST_ENGINE_P99_MAX_MS:-300}" <<'PY'
import json
import pathlib
import sys

source = pathlib.Path(sys.argv[1])
report = pathlib.Path(sys.argv[2])
errors = []

if not source.exists():
    errors.append("missing post-deploy production report")
    payload = {}
else:
    payload = json.loads(source.read_text(encoding="utf-8"))

if payload.get("status") != "passed":
    errors.append(f"post-deploy verification failed: {payload.get('status', 'unknown')}")
if not bool(payload.get("healthy", False)):
    errors.append("post-deploy health checks not green")
if not isinstance(payload.get("checks"), list) or not payload.get("checks"):
    errors.append("post-deploy checks missing")

status = "passed" if not errors else "failed"
report.write_text(json.dumps({"status": status, "observations": payload, "errors": errors}, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)
PY
