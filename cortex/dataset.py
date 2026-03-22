from __future__ import annotations

import random
import uuid
from dataclasses import asdict, dataclass, field

import pandas as pd

PHASES = ["infiltration", "reconnaissance", "lateral_movement", "escalation", "exfiltration"]
SCENARIOS = ["benign", "low_and_slow", "zero_day", "compromised_admin", "insider"]
EVENT_TYPES = ["auth", "query", "lateral_auth", "privilege_change", "bulk_read", "policy_probe"]


@dataclass
class EventRecord:
    event_id: str
    episode: int
    step: int
    timestamp: int
    scenario: str
    phase: str
    event_type: str
    source: str
    target: str
    severity: float
    trust_score: float
    novelty_score: float
    temporal_score: float
    graph_score: float
    campaign_score: float
    anomaly_score: float
    blast_radius: float
    asset_criticality: float
    label_attack: int
    metadata: dict[str, object] = field(default_factory=dict)


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def simulate_events(
    episode: int,
    num_events: int = 160,
    seed: int | None = None,
) -> list[EventRecord]:
    rng = random.Random(seed if seed is not None else episode + 1337)
    nodes = [f"ws-{idx}" for idx in range(12)] + [f"srv-{idx}" for idx in range(4)] + ["dc-0", "db-0", "admin-0", "edge-0"]
    attack_windows = {
        "benign": (0.05, 0.12),
        "low_and_slow": (0.35, 0.55),
        "zero_day": (0.55, 0.8),
        "compromised_admin": (0.65, 0.9),
        "insider": (0.45, 0.75),
    }
    events: list[EventRecord] = []
    campaign_pressure = 0.0
    for step in range(num_events):
        scenario = rng.choices(
            SCENARIOS,
            weights=[0.46, 0.16, 0.12, 0.12, 0.14],
            k=1,
        )[0]
        phase = "routine" if scenario == "benign" else PHASES[min(step * len(PHASES) // max(1, num_events), len(PHASES) - 1)]
        event_type = rng.choice(EVENT_TYPES)
        source = rng.choice(nodes)
        target = rng.choice(nodes)
        base_low, base_high = attack_windows[scenario]
        attack = 0 if scenario == "benign" else 1
        campaign_pressure = _clip(campaign_pressure * 0.94 + attack * 0.18 + rng.uniform(-0.03, 0.03))
        novelty = _clip(rng.uniform(base_low, base_high) + (0.12 if scenario == "zero_day" else 0.0))
        anomaly = _clip(rng.uniform(base_low, base_high) + (0.10 if event_type in {"privilege_change", "bulk_read"} else 0.0))
        trust = _clip(1.0 - rng.uniform(base_low, base_high) - (0.14 if scenario == "compromised_admin" else 0.0))
        temporal = _clip(campaign_pressure + rng.uniform(-0.08, 0.08))
        graph = _clip(rng.uniform(base_low, base_high) + (0.18 if phase in {"lateral_movement", "escalation"} else 0.0))
        severity = _clip(0.2 + 0.25 * attack + 0.18 * (phase == "escalation") + 0.22 * (phase == "exfiltration"))
        crown_jewel = target in {"dc-0", "db-0", "admin-0"}
        blast_radius = _clip(0.15 + 0.45 * graph + 0.20 * campaign_pressure + 0.20 * (phase in {"lateral_movement", "escalation", "exfiltration"}))
        asset_criticality = _clip(0.25 + 0.55 * crown_jewel + 0.15 * (target.startswith("srv") or target.startswith("db")))
        events.append(
            EventRecord(
                event_id=str(uuid.uuid4()),
                episode=episode,
                step=step,
                timestamp=episode * 1000 + step,
                scenario=scenario,
                phase=phase,
                event_type=event_type,
                source=source,
                target=target,
                severity=severity,
                trust_score=trust,
                novelty_score=novelty,
                temporal_score=temporal,
                graph_score=graph,
                campaign_score=campaign_pressure,
                anomaly_score=anomaly,
                blast_radius=blast_radius,
                asset_criticality=asset_criticality,
                label_attack=attack,
                metadata={"crown_jewel": crown_jewel},
            )
        )
    return events


def events_to_frame(events: list[EventRecord]) -> pd.DataFrame:
    return pd.DataFrame(asdict(event) for event in events)


def simulate_dataset(
    episodes: int = 12,
    num_events: int = 160,
    seed: int = 42,
) -> pd.DataFrame:
    all_events: list[EventRecord] = []
    for episode in range(episodes):
        all_events.extend(simulate_events(episode=episode, num_events=num_events, seed=seed + episode))
    return events_to_frame(all_events)
