#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

require_cmd git rg

PATTERN='(BEGIN (RSA|EC|OPENSSH|DSA) PRIVATE KEY|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|glpat-[A-Za-z0-9\-_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|secret[_-]?key\s*[:=]\s*["'"'"'A-Za-z0-9/_+=-]{8,}|password\s*[:=]\s*["'"'"'][^"'"'"']{8,}|token\s*[:=]\s*["'"'"'][^"'"'"']{8,})'
IGNORE='(^|/)(node_modules|\.next|\.git|artifacts|dist|build|coverage|\.venv)/'

matches_file="${REPORT_DIR}/secrets.matches"
: >"${matches_file}"

git_tracked_files | while IFS= read -r file; do
  printf '%s\n' "$file" | grep -Eq "${IGNORE}" && continue
  rg -n -H -I -e "${PATTERN}" "${ROOT_DIR}/${file}" >>"${matches_file}" || true
done

if [ -s "${matches_file}" ]; then
  python3 - "${matches_file}" "${REPORT_DIR}/secrets.json" <<'PY'
import json, sys, pathlib
matches = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="ignore").splitlines()
pathlib.Path(sys.argv[2]).write_text(json.dumps({"status": "failed", "matches": matches}, indent=2), encoding="utf-8")
PY
  fail "plaintext secret patterns found"
fi

write_json "${REPORT_DIR}/secrets.json" '{"status":"passed","matches":[]}'
log "PASS: no plaintext secrets found"

