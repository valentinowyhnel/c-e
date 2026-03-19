import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
artifacts = ROOT / "artifacts"
images_file = artifacts / "images" / "images.txt"
signatures_file = artifacts / "signatures" / "signatures.jsonl"
report_file = artifacts / "reports" / "signed-artifacts.json"
report_file.parent.mkdir(parents=True, exist_ok=True)

if not images_file.exists():
    images_file.parent.mkdir(parents=True, exist_ok=True)
    inferred = []
    for path in sorted((ROOT / "services").glob("cortex-*/Dockerfile")):
        inferred.append(f"{os.getenv('CI_REGISTRY_IMAGE', 'registry.example.com/cortex')}/{path.parent.name}:{os.getenv('CI_COMMIT_SHA', 'dev')}")
    sentinel_machine = ROOT / "services" / "python" / "cortex-sentinel-machine" / "Dockerfile"
    if sentinel_machine.exists():
        inferred.append(f"{os.getenv('CI_REGISTRY_IMAGE', 'registry.example.com/cortex')}/cortex-sentinel-machine:{os.getenv('CI_COMMIT_SHA', 'dev')}")
    images_file.write_text("\n".join(inferred) + ("\n" if inferred else ""), encoding="utf-8")
images = [line.strip() for line in images_file.read_text(encoding="utf-8").splitlines() if line.strip()]

signed = set()
if signatures_file.exists():
    for line in signatures_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("signed"):
            signed.add(payload["image"])

ratio = 1.0 if not images else len([img for img in images if img in signed]) / len(images)
minimum = float(os.getenv("MIN_SIGNED_ARTIFACTS_RATIO", "1.0"))
errors = []
if ratio < minimum:
    errors.append(f"signed artifacts ratio {ratio:.3f} below minimum {minimum:.3f}")

status = "passed" if not errors else "failed"
report_file.write_text(json.dumps({"status": status, "ratio": ratio, "images": images, "errors": errors}, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)
