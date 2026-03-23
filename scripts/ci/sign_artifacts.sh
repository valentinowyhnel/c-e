#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

require_cmd cosign

mkdir -p "${ARTIFACT_DIR}/signatures"
require_nonempty_file "${ARTIFACT_DIR}/images/images.txt"
while IFS= read -r image; do
  [ -n "${image}" ] || continue
  cosign sign --yes "${image}"
  printf '{"image":"%s","signed":true}\n' "${image}" >>"${ARTIFACT_DIR}/signatures/signatures.jsonl"
done <"${ARTIFACT_DIR}/images/images.txt"
