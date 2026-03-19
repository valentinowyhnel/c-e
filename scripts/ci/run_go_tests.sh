#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

require_cmd go python3

status="passed"
for dir in "${ROOT_DIR}"/services/cortex-*; do
  [ -f "${dir}/go.mod" ] || continue
  (cd "${dir}" && go test ./... -race)
done
write_json "${REPORT_DIR}/go-tests.json" "{\"status\":\"${status}\"}"

