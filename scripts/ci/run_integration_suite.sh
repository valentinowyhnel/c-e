#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

bash "${ROOT_DIR}/scripts/validate-runtime-api.sh"
write_json "${REPORT_DIR}/integration.json" '{"status":"passed"}'

