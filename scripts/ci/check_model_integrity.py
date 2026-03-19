import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT = ROOT / "artifacts" / "reports" / "model-integrity.json"
REPORT.parent.mkdir(parents=True, exist_ok=True)

errors: list[str] = []
schema_path = ROOT / "services/python/cortex-sentinel-machine/config/model-manifest.schema.json"
orchestrator = ROOT / "services/cortex-orchestrator/cortex_orchestrator/main.py"

if not schema_path.exists():
    errors.append("model manifest schema missing")
else:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = set(schema.get("required", []))
    for field in {"model_id", "parent_model_id", "tenant_scope", "feature_schema_hash", "signed_manifest", "rollback_pointer"}:
      if field not in required:
        errors.append(f"schema missing required field {field}")

text = orchestrator.read_text(encoding="utf-8")
for token in ("rollback_pointer", "feature_schema_hash", "signature", "x-cortex-internal-token"):
    if token not in text:
        errors.append(f"orchestrator missing guard token {token}")

status = "passed" if not errors else "failed"
REPORT.write_text(json.dumps({"status": status, "errors": errors}, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)

