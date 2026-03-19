#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

bash "${ROOT_DIR}/tests/security/gate-production-hardening.sh"
write_json "${REPORT_DIR}/resilience.json" '{"status":"passed"}'

