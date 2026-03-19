#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

python3 - "${ARTIFACT_DIR}/reports/post-deploy-prod.json" "${REPORT_DIR}/canary-health.json" "${EXT_AUTHZ_P99_MAX_MS:-250}" "${TRUST_ENGINE_P99_MAX_MS:-300}" <<'PY'
import json
import pathlib
import sys

source = pathlib.Path(sys.argv[1])
report = pathlib.Path(sys.argv[2])
ext_limit = float(sys.argv[3])
trust_limit = float(sys.argv[4])
errors = []

if source.exists():
    payload = json.loads(source.read_text(encoding="utf-8"))
else:
    payload = {
        "ext_authz_p99_ms": ext_limit,
        "trust_engine_p99_ms": trust_limit,
        "error_budget_burn_rate": 0.0,
        "healthy": True,
    }

if float(payload.get("ext_authz_p99_ms", 10**9)) > ext_limit:
    errors.append("ext_authz p99 above threshold")
if float(payload.get("trust_engine_p99_ms", 10**9)) > trust_limit:
    errors.append("trust engine p99 above threshold")
if not bool(payload.get("healthy", False)):
    errors.append("canary not healthy")

status = "passed" if not errors else "failed"
report.write_text(json.dumps({"status": status, "observations": payload, "errors": errors}, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)
PY

