#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

mkdir -p "${ARTIFACT_DIR}/packages"
tar -czf "${ARTIFACT_DIR}/packages/cortex-services-${CI_COMMIT_SHA:-local}.tgz" \
  -C "${ROOT_DIR}" services helm proto scripts

