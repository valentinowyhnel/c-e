# Cortex Production Terraform

This directory materializes the Phase 6 production scaffolding required by the product contract.

Modules present:

- `networking`
- `k8s-cluster`
- `vault-ha`
- `postgres-ha`
- `valkey`
- `neo4j`
- `nats`
- `cloudfront`
- `monitoring`

Current status:

- Interfaces and module boundaries are defined.
- Cloud resources are intentionally not applied from this workstation.
- Phase 6 is not considered passed until the modules are wired to a real AWS or Azure environment, observability is deployed, and the production checklist is validated.
