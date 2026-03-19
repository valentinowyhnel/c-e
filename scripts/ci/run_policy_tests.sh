#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

require_cmd opa python3

opa test policies --coverage --format=json >"${REPORT_DIR}/opa-coverage.json"
python3 - "${REPORT_DIR}/opa-coverage.json" "${OPA_COVERAGE_MIN:-0.80}" <<'PY'
import json
import pathlib
import sys

coverage = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
minimum = float(sys.argv[2])
covered = 0
not_covered = 0
for details in coverage.get("files", {}).values():
    covered += int(details.get("covered", 0))
    not_covered += int(details.get("not_covered", 0))
ratio = 1.0 if covered + not_covered == 0 else covered / (covered + not_covered)
if ratio < minimum:
    raise SystemExit(f"coverage {ratio:.3f} below minimum {minimum:.3f}")
PY

