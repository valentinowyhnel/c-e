#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

require_cmd syft

mkdir -p "${ARTIFACT_DIR}/sbom"
ensure_image_inventory
while IFS= read -r image; do
  [ -n "${image}" ] || continue
  name="$(printf '%s' "${image}" | tr '/:@' '_')"
  syft "${image}" -o spdx-json="${ARTIFACT_DIR}/sbom/${name}.spdx.json"
done <"${ARTIFACT_DIR}/images/images.txt"
