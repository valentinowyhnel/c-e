# Sentinel v2 Universal

## Goal

Provide a portable Sentinel v2 runtime that does not depend on:

- repository-relative Python import paths
- `uv run` at container startup
- network package downloads during pod boot
- legacy singleton Sentinel deployment semantics

## What makes this version universal

- runtime image installs the package with `pip install .`
- shared contracts fallback is embedded for packaged runtime safety
- HTTP compatibility endpoints are exposed directly by Sentinel v2:
  - `GET /health`
  - `GET /healthz`
  - `GET /readyz`
  - `POST /v1/validate-plan`
- Helm chart is parameterized with a normal `values.yaml`
- legacy Sentinel deployment is explicitly gated by `sentinelLegacy.enabled`

## Deployment source of truth

- chart: `helm/cortex-sentinel`
- workload kind: `DaemonSet`
- service: `cortex-sentinel`

## Compatibility guarantees

Existing callers can keep using:

- `http://cortex-sentinel:8080/health`
- `http://cortex-sentinel:8080/v1/validate-plan`

This preserves compatibility for:

- `cortex-orchestrator`
- `cortex-obs-agent`
- any legacy health checks still expecting a Sentinel HTTP surface

## Production expectations

For production-like environments:

- use immutable image tags
- avoid `Never` image pull policy unless images are preloaded by node management
- keep the legacy Sentinel deployment disabled
- verify the DaemonSet per node, not only the service

## Known dependency caveat

If one node stays pending while others are healthy, verify cluster networking first.
During validation, one rollout was blocked by a Calico node authorization problem on a single worker.
