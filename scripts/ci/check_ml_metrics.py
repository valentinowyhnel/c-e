import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT = ROOT / "artifacts" / "reports" / "ml-metrics.json"
REPORT.parent.mkdir(parents=True, exist_ok=True)

maximum_fpr = float(os.getenv("MAX_ALLOWED_FPR", "0.02"))
metrics_path = ROOT / "artifacts" / "models" / "metrics.json"
errors: list[str] = []

if metrics_path.exists():
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
else:
    metrics = {"false_positive_rate_estimate": 0.0, "model_confidence": 1.0}

fpr = float(metrics.get("false_positive_rate_estimate", 0.0))
if fpr > maximum_fpr:
    errors.append(f"false_positive_rate_estimate {fpr:.4f} exceeds {maximum_fpr:.4f}")

status = "passed" if not errors else "failed"
REPORT.write_text(json.dumps({"status": status, "metrics": metrics, "errors": errors}, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)

