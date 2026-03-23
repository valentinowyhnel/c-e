from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


@dataclass
class BufferedSignal:
    payload: dict[str, Any]
    received_at: float


class AgentSignalBuffer:
    def __init__(self, maxlen: int = 32, ttl_seconds: float = 120.0) -> None:
        self.maxlen = maxlen
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, deque[BufferedSignal]] = defaultdict(lambda: deque(maxlen=maxlen))

    def add(self, payload: dict[str, Any]) -> None:
        entity_id = str(payload.get("entity_id") or "")
        if not entity_id:
            return
        self._items[entity_id].append(BufferedSignal(payload=payload, received_at=time.time()))

    def recent(self, entity_id: str) -> list[dict[str, Any]]:
        now = time.time()
        queue = self._items.get(entity_id, deque())
        while queue and now - queue[0].received_at > self.ttl_seconds:
            queue.popleft()
        return [item.payload for item in queue]


class SentinelMetaDecisionBridge:
    def __init__(self, timeout_ms: int = 20) -> None:
        self.timeout_ms = timeout_ms
        self.signals = AgentSignalBuffer()

    def ingest_signal(self, payload: dict[str, Any]) -> None:
        self.signals.add(payload)

    def evaluate(self, *, entity_id: str, state_score: float, events: list[Any], context: str) -> dict[str, Any] | None:
        started = time.monotonic()
        messages = self.signals.recent(entity_id)
        if not messages:
            return None
        trust_scores: dict[str, float] = {}
        weighted = 0.0
        trust_total = 0.0
        raw_scores = []
        selected_agents = []
        for message in messages:
            agent_id = str(message.get("agent_id"))
            runtime_trust = _clamp(float(message.get("runtime_trust", 0.5)))
            data_quality = _clamp(float(message.get("data_quality", 0.5)))
            reasoning_quality = _clamp(float(message.get("reasoning_quality", 0.5)))
            uncertainty = _clamp(float(message.get("uncertainty", 0.5)))
            specialty_bonus = 0.1 if message.get("specialty") in {"response_decision", "containment_planning", "identity_graph"} else 0.0
            trust = _clamp(0.32 + 0.26 * runtime_trust + 0.14 * data_quality + 0.14 * reasoning_quality + specialty_bonus - 0.18 * uncertainty)
            trust_scores[agent_id] = trust
            signal = _clamp(float(message.get("risk_signal", 0.0)))
            raw_scores.append(signal)
            if trust >= 0.45:
                weighted += signal * trust
                trust_total += trust
                selected_agents.append(agent_id)
        aggregate_risk = _clamp(weighted / trust_total) if trust_total else 0.0
        spread = max(raw_scores) - min(raw_scores) if raw_scores else 0.0
        mean_signal = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0
        disagreement = sum(abs(score - mean_signal) for score in raw_scores) / len(raw_scores) if raw_scores else 0.0
        conflict_score = _clamp(0.6 * spread + 0.4 * disagreement)
        criticality = _clamp((100.0 - state_score) / 100.0)
        novelty = _clamp(max((getattr(event, "severity", 0.0) for event in events), default=0.0))
        deep_analysis_reasons = []
        if conflict_score >= 0.55:
            deep_analysis_reasons.append("agent_conflict")
        if min(trust_scores.values(), default=1.0) < 0.45:
            deep_analysis_reasons.append("low_agent_trust")
        if novelty >= 0.7:
            deep_analysis_reasons.append("high_novelty")
        if context in {"crown_jewel_access", "identity_store", "payment_data"}:
            deep_analysis_reasons.append("critical_asset")
        deep_analysis_triggered = bool(deep_analysis_reasons)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        degraded_mode = elapsed_ms > self.timeout_ms
        if degraded_mode:
            aggregate_risk = _clamp(sum(raw_scores) / len(raw_scores)) if raw_scores else 0.0
            deep_analysis_triggered = False
            deep_analysis_reasons = []
        return {
            "weighted_scores": {"aggregate_risk": aggregate_risk},
            "agent_trust_scores": trust_scores,
            "conflict_score": conflict_score,
            "selected_agents": selected_agents,
            "deep_analysis_triggered": deep_analysis_triggered,
            "reasoning_summary": f"aggregate_risk={aggregate_risk:.3f} conflict={conflict_score:.3f}",
            "deep_analysis_requests": [
                {
                    "entity_id": entity_id,
                    "agent_id": agent_id,
                    "reasons": deep_analysis_reasons,
                    "deadline_ms": 150,
                }
                for agent_id in selected_agents
            ] if deep_analysis_triggered else [],
            "audit_log": {
                "entity_id": entity_id,
                "agent_count": len(messages),
                "elapsed_ms": elapsed_ms,
                "deep_analysis_reasons": deep_analysis_reasons,
            },
            "degraded_mode": degraded_mode,
        }
