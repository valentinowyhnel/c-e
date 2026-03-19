#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
ARTIFACT_DIR="${ARTIFACT_DIR:-${ROOT_DIR}/artifacts}"
REPORT_DIR="${REPORT_DIR:-${ARTIFACT_DIR}/reports}"

mkdir -p "${ARTIFACT_DIR}" "${REPORT_DIR}"

log() {
  printf '%s\n' "$*"
}

fail() {
  log "FAIL: $*"
  exit 1
}

require_cmd() {
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || fail "missing command: ${cmd}"
  done
}

write_json() {
  target="$1"
  content="$2"
  mkdir -p "$(dirname "${target}")"
  printf '%s\n' "${content}" >"${target}"
}

compare_float() {
  left="$1"
  op="$2"
  right="$3"
  python3 - "$left" "$op" "$right" <<'PY'
import sys
left = float(sys.argv[1])
op = sys.argv[2]
right = float(sys.argv[3])
result = {
    "<=": left <= right,
    "<": left < right,
    ">=": left >= right,
    ">": left > right,
    "==": left == right,
}[op]
raise SystemExit(0 if result else 1)
PY
}

git_tracked_files() {
  git -C "${ROOT_DIR}" ls-files
}

ensure_image_inventory() {
  images_file="${ARTIFACT_DIR}/images/images.txt"
  mkdir -p "${ARTIFACT_DIR}/images"
  if [ -f "${images_file}" ] && [ -s "${images_file}" ]; then
    return 0
  fi
  : >"${images_file}"
  for dir in "${ROOT_DIR}"/services/cortex-* "${ROOT_DIR}"/services/python/cortex-sentinel-machine; do
    [ -f "${dir}/Dockerfile" ] || continue
    name="$(basename "${dir}")"
    printf '%s/%s:%s\n' "${CI_REGISTRY_IMAGE:-registry.example.com/cortex}" "${name}" "${CI_COMMIT_SHA:-dev}" >>"${images_file}"
  done
}
