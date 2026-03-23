import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
artifacts = ROOT / "artifacts"
images_file = artifacts / "images" / "images.txt"
signatures_file = artifacts / "signatures" / "signatures.jsonl"
report_file = artifacts / "reports" / "signed-artifacts.json"
report_file.parent.mkdir(parents=True, exist_ok=True)

errors = []
if not images_file.exists():
    errors.append(f"missing image inventory {images_file.relative_to(ROOT)}")
    images = []
else:
    images = [line.strip() for line in images_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not images:
        errors.append("image inventory is empty")

signed = set()
if signatures_file.exists():
    for line in signatures_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("signed"):
            signed.add(payload["image"])
else:
    errors.append(f"missing signatures manifest {signatures_file.relative_to(ROOT)}")

ratio = 1.0 if not images else len([img for img in images if img in signed]) / len(images)
minimum = float(os.getenv("MIN_SIGNED_ARTIFACTS_RATIO", "1.0"))
if ratio < minimum:
    errors.append(f"signed artifacts ratio {ratio:.3f} below minimum {minimum:.3f}")

verified: dict[str, str] = {}
cosign_key = os.getenv("COSIGN_PUBLIC_KEY")
for image in images:
    if image not in signed:
        continue
    cmd = ["cosign", "verify"]
    if cosign_key:
        cmd.extend(["--key", cosign_key])
    else:
        cmd.append("--keyless")
    cmd.append(image)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    verified[image] = "passed" if proc.returncode == 0 else "failed"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        message = detail[-1] if detail else "cosign verify failed"
        errors.append(f"{image}: {message}")

status = "passed" if not errors else "failed"
report_file.write_text(
    json.dumps({"status": status, "ratio": ratio, "images": images, "verified": verified, "errors": errors}, indent=2),
    encoding="utf-8",
)
if errors:
    raise SystemExit(1)
