import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT = ROOT / "artifacts" / "reports" / "rollback-readiness.json"
REPORT.parent.mkdir(parents=True, exist_ok=True)
errors: list[str] = []

required_files = [
    ROOT / "scripts/ci/deploy_prod_canary.sh",
    ROOT / "scripts/ci/promote_release.sh",
    ROOT / "services/python/cortex-sentinel-machine/RUNBOOK.md",
    ROOT / "services/cortex-orchestrator/cortex_orchestrator/main.py",
]
for path in required_files:
    if not path.exists():
        errors.append(f"missing file {path.relative_to(ROOT)}")

orch = (ROOT / "services/cortex-orchestrator/cortex_orchestrator/main.py").read_text(encoding="utf-8")
if "rollback_pointer" not in orch:
    errors.append("orchestrator missing rollback_pointer support")

status = "passed" if not errors else "failed"
REPORT.write_text(json.dumps({"status": status, "errors": errors}, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)

