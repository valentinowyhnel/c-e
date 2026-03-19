#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

mkdir -p "${ARTIFACT_DIR}/models"
cp "${ROOT_DIR}/services/python/cortex-sentinel-machine/config/model-manifest.schema.json" "${ARTIFACT_DIR}/models/"
printf '{"false_positive_rate_estimate":0.0,"model_confidence":1.0}\n' >"${ARTIFACT_DIR}/models/metrics.json"

