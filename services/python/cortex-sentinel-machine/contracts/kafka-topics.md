# Bus Contracts

- `cortex.obs.stream`
  - key: `machine_id:event_id`
  - value: normalized redacted event summary
- `cortex.trust.updates`
  - key: `machine_id:event_id`
  - value: local calibrated risk signal with drift flags
- `cortex.obs.anomalies`
  - key: `tenant_id:machine_id:model_id`
  - value: clipped local model delta plus suspicion score
- `cortex.security.events`
  - key: `tenant_id:machine_id:timestamp`
  - value: auditable policy/model/promotion decision
