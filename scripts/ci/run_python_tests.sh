#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

require_cmd python3

python3 - "${ROOT_DIR}" "${REPORT_DIR}/python-tests.json" <<'PY'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
report = pathlib.Path(sys.argv[2])
errors = []

for service in sorted(root.glob("services/*")) + sorted(root.glob("services/python/*")):
    pyproject = service / "pyproject.toml"
    tests = service / "tests"
    if not pyproject.exists() or not tests.exists():
        continue
    cmd = [sys.executable, "-m", "pytest", str(tests)]
    proc = subprocess.run(cmd, cwd=service, text=True)
    if proc.returncode != 0:
        errors.append(f"{service.relative_to(root)} pytest failed")

status = "passed" if not errors else "failed"
report.write_text(json.dumps({"status": status, "errors": errors}, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)
PY

