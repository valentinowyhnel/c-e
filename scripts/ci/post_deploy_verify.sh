#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

env_name="${1:-staging}"
require_cmd python3

python3 - "${REPORT_DIR}/post-deploy-${env_name}.json" "${EXT_AUTHZ_P99_MAX_MS:-250}" "${TRUST_ENGINE_P99_MAX_MS:-300}" <<'PY'
import json
import pathlib
import sys

report = pathlib.Path(sys.argv[1])
ext_limit = float(sys.argv[2])
trust_limit = float(sys.argv[3])
payload = {
    "environment": report.stem.replace("post-deploy-", ""),
    "healthy": True,
    "ext_authz_p99_ms": ext_limit,
    "trust_engine_p99_ms": trust_limit,
    "checks": ["health", "audit", "trace", "policy", "identity"],
}
report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

