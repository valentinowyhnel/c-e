#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

require_cmd opa python3

coverage_json="${REPORT_DIR}/opa-coverage-raw.json"
opa test policies --coverage --format=json >"${coverage_json}"

python3 - "${coverage_json}" "${REPORT_DIR}/policy-regression.json" "${OPA_COVERAGE_MIN:-0.80}" <<'PY'
import json
import pathlib
import sys

coverage_path = pathlib.Path(sys.argv[1])
report_path = pathlib.Path(sys.argv[2])
minimum = float(sys.argv[3])
payload = json.loads(coverage_path.read_text(encoding="utf-8"))

files = payload.get("files", {})
covered = 0
not_covered = 0
for details in files.values():
    covered += int(details.get("covered", 0))
    not_covered += int(details.get("not_covered", 0))

total = covered + not_covered
ratio = 1.0 if total == 0 else covered / total
tests_present = bool(payload.get("result"))
errors = []
if not tests_present:
    errors.append("no OPA tests discovered")
if ratio < minimum:
    errors.append(f"coverage {ratio:.3f} below minimum {minimum:.3f}")

status = "passed" if not errors else "failed"
report_path.write_text(json.dumps({"status": status, "coverage": ratio, "minimum": minimum, "errors": errors}, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)
PY

