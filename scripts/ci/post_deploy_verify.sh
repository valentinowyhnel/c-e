#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

env_name="${1:-staging}"
release_name="${HELM_RELEASE_NAME}-${env_name}"
status_file="${ARTIFACT_DIR}/helm-status-${env_name}.json"
require_cmd helm kubectl python3

helm status "${release_name}" --namespace "${KUBE_NAMESPACE}" -o json >"${status_file}"

python3 - "${status_file}" "${REPORT_DIR}/post-deploy-${env_name}.json" "${KUBE_NAMESPACE}" "${release_name}" <<'PY'
import json
import pathlib
import sys
import subprocess

status_file = pathlib.Path(sys.argv[1])
report = pathlib.Path(sys.argv[2])
namespace = sys.argv[3]
release_name = sys.argv[4]
expected_deployments = (
    "cortex-victoriametrics",
    "opentelemetry-collector",
    "bloodhound-ce",
)

helm_status = json.loads(status_file.read_text(encoding="utf-8"))
errors: list[str] = []
checks: list[dict[str, object]] = []

release_info = {
    "name": helm_status.get("name", release_name),
    "namespace": helm_status.get("namespace", namespace),
    "status": helm_status.get("info", {}).get("status", "unknown"),
    "revision": helm_status.get("version"),
}
if release_info["status"] != "deployed":
    errors.append(f"helm release not deployed: {release_info['status']}")

for deployment in expected_deployments:
    proc = subprocess.run(
        [
            "kubectl",
            "get",
            "deployment",
            deployment,
            "-n",
            namespace,
            "-o",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        errors.append(f"missing deployment {deployment}")
        checks.append({"name": deployment, "healthy": False, "reason": "missing"})
        continue

    payload = json.loads(proc.stdout)
    spec = payload.get("spec", {})
    status = payload.get("status", {})
    desired = int(spec.get("replicas", 1))
    ready = int(status.get("readyReplicas", 0))
    available = int(status.get("availableReplicas", 0))
    observed_generation = int(status.get("observedGeneration", 0))
    generation = int(payload.get("metadata", {}).get("generation", 0))
    healthy = ready >= desired and available >= desired and observed_generation >= generation
    if not healthy:
        errors.append(
            f"deployment {deployment} not ready (desired={desired}, ready={ready}, available={available})"
        )
    checks.append(
        {
            "name": deployment,
            "healthy": healthy,
            "desired_replicas": desired,
            "ready_replicas": ready,
            "available_replicas": available,
            "observed_generation": observed_generation,
            "generation": generation,
        }
    )

payload = {
    "environment": report.stem.replace("post-deploy-", ""),
    "status": "passed" if not errors else "failed",
    "healthy": not errors,
    "release": release_info,
    "checks": checks,
    "errors": errors,
}
report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
if errors:
    raise SystemExit(1)
PY
