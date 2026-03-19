#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

python3 - "${ROOT_DIR}" "${REPORT_DIR}/trace-propagation.json" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
report = pathlib.Path(sys.argv[2])
errors = []

checks = {
    root / "proto/sentinel/v1/sentinel_machine.proto": ["trace_id"],
    root / "services/cortex-gateway/internal/httpapi/handler.go": ["trace_id"],
    root / "services/python/cortex-sentinel-machine/app/service.py": ["trace_id"],
    root / "services/python/cortex-sentinel-machine/app/cortex/contracts.py": ["trace_id"],
}

for path, markers in checks.items():
    text = path.read_text(encoding="utf-8")
    for marker in markers:
        if marker not in text:
            errors.append(f"{path.relative_to(root)} missing {marker}")

status = "passed" if not errors else "failed"
report.write_text(json.dumps({"status": status, "errors": errors}, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)
PY

