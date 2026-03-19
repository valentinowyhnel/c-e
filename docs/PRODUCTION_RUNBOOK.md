# Phase 6 Runbook

## Goal

Move Cortex from local validated stack to first production-ready environment without violating the security contract.

## Sequence

1. Apply `infra/terraform` in a dedicated cloud account.
2. Bootstrap Kubernetes access, namespaces and baseline policies.
3. Deploy Vault HA and validate cloud KMS auto-unseal.
4. Deploy SPIRE with production trust domain and durable storage.
5. Deploy identity, enforcement, agents and console charts with production values.
6. Deploy observability and confirm traces, metrics and logs.
7. Run production security gates and capture evidence.

## Helm production guardrails

Each critical chart now propagates `CORTEX_ENVIRONMENT` and refuses unsafe production renders.

Production rules enforced at Helm template time:

- internal API secrets must be marked as required
- console self-call secret must be marked as required
- image tags cannot be `dev`, `latest` or empty
- observability workloads cannot keep mixed dev tags in production

Set these explicitly in production values files:

```yaml
environment: prod
internalApi:
  required: true
consoleInternal:
  required: true
```

Reference production values templates are provided in:

- `helm/cortex-trust-engine/values-prod.example.yaml`
- `helm/cortex-mcp-server/values-prod.example.yaml`
- `helm/cortex-console/values-prod.example.yaml`
- `helm/cortex-observability/values-prod.example.yaml`

## Internal API hardening

Sensitive internal APIs are designed to stay open in local mode and become authenticated in pre-production or production when `CORTEX_INTERNAL_API_TOKEN` is configured.

### Secrets to provision before Helm upgrade

Create a shared secret for protected inter-service APIs:

```bash
kubectl -n cortex-system create secret generic cortex-internal-api \
  --from-literal=token='<strong-random-token>'
```

Create a dedicated secret for console self-calls:

```bash
kubectl -n cortex-system create secret generic cortex-console-internal \
  --from-literal=token='<different-strong-random-token>'
```

### Services protected by the shared token

- `cortex-trust-engine`
- `cortex-audit`
- `cortex-approval`
- `cortex-obs-agent`
- `cortex-console` outbound calls
- `cortex-mcp-server` outbound calls to trust

### Endpoints that remain open for probes only

- `GET /health`
- `GET /healthz`
- `GET /readyz`
- console `GET /api/health`

All other sensitive HTTP routes should be considered protected once the token is present in the deployment environment.

### Verification after deploy

1. Confirm the environment variable is present in each protected pod.
2. Call a sensitive endpoint without `x-cortex-internal-token` and expect `401`.
3. Call the same endpoint with the header and expect success.
4. Confirm console dashboards, approvals, events and decision pages still load.
5. Run `tests/security/gate-production-hardening.sh`.

## Capability maturity gate

`scripts/runtime/check-production-maturity.py` is intentionally strict.

It fails if a production-critical capability is still marked:

- `preprod_ready`
- `beta`
- `experimental`
- `stubbed`

Today this is expected to block full production promotion until the remaining capabilities are either hardened to `production_ready` or explicitly removed from the production scope.

## Exit criteria

- All production checklist blockers are closed.
- `tests/security/gate-phase6.sh` passes.
- `tests/security/gate-production-hardening.sh` passes.
- `tests/security/gate-final.sh` passes.
