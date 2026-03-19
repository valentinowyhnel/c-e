# Event Contract

Each outbound event contains:

- `event_id`
- `machine_id`
- `tenant_id`
- `session_local_id`
- `event_type`
- `event_time`
- `process_lineage_summary`
- `feature_vector`
- `integrity_fields`
- `confidence_local`
- `privacy_level`
- `trace_id`

Privacy rules:

- no raw file contents
- no raw memory
- no unredacted credentials
- no direct user document payloads

