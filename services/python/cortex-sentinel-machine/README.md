# Cortex Sentinel Machine

Sentinel Machine is the endpoint sensor and local adaptive layer of Cortex. It collects low-overhead local signals, redacts them locally, computes multi-stage anomaly scores, trains a local shadow model, and emits only validated summaries and signed model metadata toward Cortex.

## Architecture

- `collector/`: local signal ingestion adapters
- `normalizer/`: redaction and schema normalization
- `features/`: feature extraction and rarity/burst tracking
- `scoring/`: online half-space style scoring, robust deviation scoring, severity calibration
- `drift/`: ADWIN-like and Page-Hinkley drift detection
- `training/`: short-memory and long-memory local training
- `learning_guard/`: anti-poisoning and replay protection
- `promotion/`: champion/challenger/shadow governance
- `transport/`: encrypted WAL queue and topic emission
- `policy/`: signed policy verification
- `audit/`: mandatory security-decision audit trail

## Quick Start

```bash
cd services/python/cortex-sentinel-machine
python -m pip install -e .
pytest
python -m app.main
python -m app.serve
```

## Transport modes

- `SENTINEL_GRPC_TLS_MODE=dev-insecure`: local development only
- `SENTINEL_GRPC_TLS_MODE=mtls`: requires PEM files for server cert, server key, and client CA
- stub generation is explicit via `python scripts/generate_proto_stubs.py` and fails closed if `grpc_tools` is absent

## Cortex integration

- ingest gateway target: `POST /v1/sentinel/events`
- trust engine target: `POST /trust/evaluate/v2`
- model orchestrator target: `POST /v1/model/promote`
- internal control-plane calls carry `x-cortex-internal-token`
- bus subjects aligned with current Cortex paper: `cortex.obs.stream`, `cortex.trust.updates`, `cortex.security.events`
- optional runtime NATS/JetStream publish is disabled by default in local runs and enabled with `SENTINEL_ENABLE_NATS_BUS=1`
- if NATS is down, records remain in the encrypted WAL until `flush_pending` succeeds
- runtime command subject: `cortex.sentinel.commands`
- supported commands: `flush_pending`, `disable_nats_bus`, `sync_shadow`

## Security invariants

- fail-closed on policy verification
- no unsigned model manifest acceptance
- no critical action without Cortex approval
- no raw sensitive payloads emitted
- no naive averaging of local updates
- suspicious or replayed updates are quarantined
- gRPC ingest supports peer validation via SPIFFE metadata guards
- `/health` and `/metrics` require a bearer token

## Mandatory tests

- local redaction
- offline local scoring
- drift triggering
- shadow model training without champion overwrite
- model rollback pointer preservation
- unsigned update rejection path
- replay rejection
- adversarial extreme update quarantine
- queue durability and budget health
