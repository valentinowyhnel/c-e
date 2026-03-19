#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

require_cmd docker

mkdir -p "${ARTIFACT_DIR}/images"
: >"${ARTIFACT_DIR}/images/images.txt"

for dir in "${ROOT_DIR}"/services/cortex-* "${ROOT_DIR}"/services/python/cortex-sentinel-machine; do
  [ -f "${dir}/Dockerfile" ] || continue
  name="$(basename "${dir}")"
  image="${CI_REGISTRY_IMAGE:-registry.example.com/cortex}/${name}:${CI_COMMIT_SHA:-dev}"
  docker build -t "${image}" "${dir}"
  printf '%s\n' "${image}" >>"${ARTIFACT_DIR}/images/images.txt"
done
