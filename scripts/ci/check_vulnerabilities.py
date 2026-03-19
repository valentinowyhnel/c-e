import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT = ROOT / "artifacts" / "reports" / "vulnerabilities.json"
REPORT.parent.mkdir(parents=True, exist_ok=True)

max_critical = int(os.getenv("MAX_CRITICAL_VULNERABILITIES", "0"))
trivy_path = ROOT / "artifacts" / "security" / "trivy.json"
errors: list[str] = []

critical = 0
if trivy_path.exists():
    payload = json.loads(trivy_path.read_text(encoding="utf-8"))
    for result in payload.get("Results", []):
        for vuln in result.get("Vulnerabilities", []) or []:
            if vuln.get("Severity") == "CRITICAL":
                critical += 1

if critical > max_critical:
    errors.append(f"critical vulnerabilities {critical} exceed {max_critical}")

status = "passed" if not errors else "failed"
REPORT.write_text(json.dumps({"status": status, "critical": critical, "max_allowed": max_critical, "errors": errors}, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)
