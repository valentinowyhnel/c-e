# Cortex Agents Training Report 2026-03-22

## Scope

Long training run executed for the non-decision agents in the modular `cortex/` package:

- `sentinel`
- `threat_hunter`
- `trust`
- `graph`
- `anomaly`

The decision agent was intentionally excluded.

## Runtime

- requested episodes: `24`
- executed episodes: `11`
- stopping condition: `early stopping`
- export directory:
  - `test-artifacts/cortex-agents-train-long-20260322`

## Global Metrics

- precision: `0.5540`
- recall: `0.5808`
- average_reward: `30.4246`
- final_reward: `39.5289`
- improvement: `29.6825`
- convergence_gap: `17.2612`

## Agent Weight Evolution

### Threat Hunter

- before:
  - `novelty_score=0.55`
  - `anomaly_score=0.20`
  - `campaign_score=0.15`
  - `graph_score=0.10`
- after:
  - `novelty_score=0.6008`
  - `anomaly_score=0.2420`
  - `campaign_score=0.1597`
  - `graph_score=0.1199`

### Trust

- before:
  - `trust_risk=0.70`
  - `novelty_score=0.10`
  - `graph_score=0.10`
  - `campaign_score=0.10`
- after:
  - `trust_risk=0.7510`
  - `novelty_score=0.1508`
  - `graph_score=0.1199`
  - `campaign_score=0.1097`

### Graph

- before:
  - `graph_score=0.55`
  - `temporal_score=0.15`
  - `campaign_score=0.20`
  - `anomaly_score=0.10`
- after:
  - `graph_score=0.5699`
  - `temporal_score=0.1578`
  - `campaign_score=0.2097`
  - `anomaly_score=0.1420`

### Anomaly

- before:
  - `anomaly_score=0.65`
  - `novelty_score=0.15`
  - `temporal_score=0.10`
  - `campaign_score=0.10`
- after:
  - `anomaly_score=0.6920`
  - `novelty_score=0.2008`
  - `temporal_score=0.1078`
  - `campaign_score=0.1097`

## Interpretation

- `SentinelRL` improved strongly on reward during the run.
- `ThreatHunter` shifted toward stronger novelty and anomaly sensitivity.
- `Trust` increased emphasis on `trust_risk`, which is the expected direction.
- `Graph` and `Anomaly` both increased their main structural signal while remaining relatively stable.

## Operational Note

This run validates the local continuous learning loop and the reward shaping logic.

It does **not** by itself promote these agents into autonomous production authority.
They remain bounded by Cortex policy, trust, approval and degraded-mode controls.
