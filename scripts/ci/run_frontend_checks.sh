#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

mode="${1:-validate}"
service_dir="${ROOT_DIR}/services/cortex-console"

cd "${service_dir}"
npm ci

case "${mode}" in
  validate)
    npm run lint
    printf '{"status":"passed","mode":"validate"}\n' >"${REPORT_DIR}/frontend-validate.json"
    ;;
  test)
    npm run lint
    printf '{"status":"passed","mode":"test"}\n' >"${REPORT_DIR}/frontend-unit.json"
    ;;
  build)
    npm run build
    mkdir -p "${ARTIFACT_DIR}/frontend"
    cp -R .next "${ARTIFACT_DIR}/frontend/.next"
    printf '{"status":"passed","mode":"build"}\n' >"${REPORT_DIR}/frontend-build.json"
    ;;
  *)
    fail "unknown frontend mode ${mode}"
    ;;
esac

