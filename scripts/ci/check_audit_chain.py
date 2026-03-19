import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT = ROOT / "artifacts" / "reports" / "audit-chain.json"
REPORT.parent.mkdir(parents=True, exist_ok=True)

errors: list[str] = []

audit_main = ROOT / "services/cortex-audit/cortex_audit/main.py"
gateway = ROOT / "services/cortex-gateway/internal/httpapi/handler.go"
orchestrator = ROOT / "services/cortex-orchestrator/cortex_orchestrator/main.py"
docs = ROOT / "docs/PRODUCTION_CHECKLIST.md"

for path, markers in {
    audit_main: ["CREATE TABLE IF NOT EXISTS audit_events", "/v1/events", "event_id"],
    gateway: ["appendAudit", "trace_id"],
    orchestrator: ["_append_model_audit", "rollback_pointer"],
    docs: ["Immutable, signed audit pipeline validated"],
}.items():
    text = path.read_text(encoding="utf-8")
    for marker in markers:
        if marker not in text:
            errors.append(f"{path.relative_to(ROOT)} missing marker {marker}")

status = "passed" if not errors else "failed"
REPORT.write_text(json.dumps({"status": status, "errors": errors}, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)

