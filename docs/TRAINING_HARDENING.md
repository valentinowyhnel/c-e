# Training Hardening

## Goal

Train Cortex on real-world defensive attack knowledge without:

- re-ingesting attacks already covered by the knowledge base
- feeding raw weaponized payloads into the agent training loop
- mixing advisory model enrichment with execution authority

## Current implementation

Implemented:

- `cortex-sentinel-machine` now provides a defensive corpus curator
- novelty filtering by fingerprint and semantic overlap
- unsafe offensive marker rejection
- routing of accepted samples toward the relevant agent families
- CLI builder: `python scripts/runtime/build-attack-training-plan.py`
- internal-source builder: `python scripts/runtime/build-internal-training-plan.py`
- supported internal sources:
  - `cortex-audit` incident events
  - `cortex.ad.drifts`
  - BloodHound attack-path summaries
  - normalized SOC reports

Partially operational:

- training plan generation for `decision`, `remediation`, `ad`, `observer`, `soc`
- governance visibility in the console models page
- live export automation from running services is still environment-dependent

Conceptual / roadmap:

- automated corpus fetch from external intel sources
- embedding-based duplicate detection at large scale
- signed corpus provenance pipeline with human review workflow

## Safety invariants

- no raw offensive payload corpus should be accepted as-is
- already-known attacks should be skipped, not retrained
- no model assignment change grants execution authority
- decision models remain advisory-first

## Sample workflow

1. Prepare a JSON array of attack summaries with:
   - `sample_id`
   - `title`
   - `summary`
   - `source`
   - `content`
   - `technique_ids`
   - `tags`
   - optional `family`
2. Export the known registry if available.
3. Run:

```bash
python scripts/runtime/build-attack-training-plan.py samples.json --known known.json --output plan.json
```

4. Review:
   - `accepted`
   - `skipped_known`
   - `rejected`
   - `agent_queues`

## Internal-source workflow

```bash
python scripts/runtime/build-internal-training-plan.py \
  --audit audit-events.json \
  --drifts ad-drifts.json \
  --attack-paths bloodhound-paths.json \
  --soc-reports soc-reports.json \
  --known known.json \
  --output internal-plan.json
```

## Why this is safer

The filter refuses to treat Cortex as a sink for arbitrary offensive material. It only keeps high-signal, tagged, novel defensive knowledge that improves:

- privilege review
- containment reasoning
- AD misuse detection
- telemetry correlation
- analyst investigation
