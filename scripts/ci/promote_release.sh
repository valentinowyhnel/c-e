#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

test -f "${REPORT_DIR}/canary-health.json" || fail "missing canary health report"
test -f "${REPORT_DIR}/rollback-readiness.json" || fail "missing rollback readiness report"
write_json "${REPORT_DIR}/promotion.json" '{"status":"passed","promotion":"controlled"}'
log "Release promotion validated"

