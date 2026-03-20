# Phase 6 Production Checklist

This checklist tracks the non-negotiable production requirements from the Cortex product contract.

## Current assessment

- Status: `phase-6-local-passed`
- Last reviewed: `2026-03-19`
- Local Kind stack: available
- Cloud production environment: not provisioned
- Current session runtime validation: `blocked` (`kubectl` current-context unset)
- Latest successful runtime hardening validation: `2026-03-18` on local Kind
- Latest local code verification: `2026-03-19` (`44 passed`, Python compile OK)
- Latest runtime component verification: `2026-03-19` on local Kind via explicit `--kubeconfig`

## Checklist

- `pending` Vault HA with 3 Raft nodes and cloud KMS auto-unseal
- `pending` TLS everywhere via cert-manager and production PKI
- `passed-local` NetworkPolicies validated in local Kind
- `pending` SPIRE root CA anchored on HSM
- `pending` Secret rotation exercised without downtime
- `pending` Disaster recovery tested end-to-end in under 30 minutes
- `pending` External penetration test on Envoy, MCP Gateway and Console SOC
- `pending` Immutable, signed audit pipeline validated
- `pending` Rate limits tested under production load
- `pending` vLLM model supply-chain review documented
- `passed-local` Defensive training curation skips known attacks and rejects raw offensive payload markers
- `pending` Dependency vulnerability review clean in production images
- `pending` SBOM generated for each production image
- `pending` SOC 2 Type 1 evidence package assembled
- `passed-preprod` Shared internal API secret `cortex-internal-api` provisioned in `cortex-system`
- `passed-preprod` Console self-call secret `cortex-console-internal` provisioned in `cortex-system`
- `passed-preprod` Sensitive internal HTTP routes return `401/403` without `x-cortex-internal-token` and `200` with token
- `passed-preprod` Console-to-service flows validated with internal token enabled
- `passed-preprod` Helm charts fail closed in `prod` when internal API secrets are not required
- `passed-preprod` Helm charts fail closed in `prod` when image tags are `dev`, `latest` or empty
- `pending` Production-only capability gate passes with all critical capabilities marked `production_ready`

## Blocking gaps

- `passed-local` OpenTelemetry Collector + VictoriaMetrics + agentic observability stack
- `passed-local` Human approval service deployed in local Kind
- `passed-local` Dedicated audit service deployed in local Kind
- `missing` Cloud infrastructure apply and environment-specific values
- `passed-preprod` Sentinel v2 DaemonSet rolled out on 3 nodes after runtime packaging and legacy-service cleanup
