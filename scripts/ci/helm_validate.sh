#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

require_cmd helm

for chart in "${ROOT_DIR}"/helm/cortex-* "${ROOT_DIR}"/helm/cortex-ci-smoke; do
  [ -d "${chart}" ] || continue
  helm lint "${chart}" --strict
done
write_json "${REPORT_DIR}/helm-lint.json" '{"status":"passed"}'

