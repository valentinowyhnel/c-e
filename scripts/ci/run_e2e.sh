#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

bash "${ROOT_DIR}/tests/security/gate-api.sh"
write_json "${REPORT_DIR}/e2e.json" '{"status":"passed"}'

