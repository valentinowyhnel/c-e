from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import pandas as pd

from cortex.meta_decision.analysis_fingerprint_engine import AnalysisFingerprintEngine
from cortex.meta_decision.agent_trust_registry import AgentTrustRegistry
from cortex.meta_decision.case_memory_store import CaseMemoryStore
from cortex.meta_decision.decision_trust_engine import DecisionTrustEngine


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


@dataclass
class LearningMemory:
    maxlen: int = 5000
    items: deque[dict[str, object]] = field(default_factory=lambda: deque(maxlen=5000))

    def add(self, item: dict[str, object]) -> None:
        self.items.append(item)

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(list(self.items)) if self.items else pd.DataFrame()


class ContinuousLearningEngine:
    def __init__(
        self,
        *,
        trust_registry: AgentTrustRegistry,
        decision_trust_engine: DecisionTrustEngine,
        case_memory_store: CaseMemoryStore | None = None,
        sentinel_rl: object | None = None,
    ) -> None:
        self.trust_registry = trust_registry
        self.decision_trust_engine = decision_trust_engine
        self.case_memory_store = case_memory_store or CaseMemoryStore()
        self.sentinel_rl = sentinel_rl
        self.memory = LearningMemory()
        self.fingerprint_engine = AnalysisFingerprintEngine()

    def update_agent_performance(
        self,
        *,
        agent_id: str,
        specialty: str,
        correct: bool,
        confidence: float,
    ) -> None:
        self.trust_registry.record_case_outcome(
            agent_id,
            specialty=specialty,
            correct=correct,
            confidence=confidence,
        )

    def adjust_agent_trust(self, agent_id: str) -> float:
        profile = self.trust_registry.get_profile(agent_id)
        historical = (
            sum(profile.historical_accuracy.values()) / len(profile.historical_accuracy)
            if profile.historical_accuracy
            else profile.base_trust
        )
        adjusted = _clamp(0.45 * profile.base_trust + 0.35 * profile.runtime_trust + 0.20 * historical - 0.20 * profile.drift_score)
        self.trust_registry.update_base_trust(agent_id, adjusted)
        return adjusted

    def detect_agent_drift(self, agent_id: str, window: int = 8) -> float:
        profile = self.trust_registry.get_profile(agent_id)
        history = [entry["updated_accuracy"] for entry in profile.performance_history[-window * 2 :]]
        if len(history) < window * 2:
            return profile.drift_score
        previous = sum(history[:window]) / window
        current = sum(history[window:]) / window
        drift = _clamp(abs(current - previous))
        self.trust_registry.update_drift(agent_id, drift)
        return drift

    def detect_drift(self, agent_id: str, window: int = 8) -> float:
        return self.detect_agent_drift(agent_id, window=window)

    def remember_case(
        self,
        *,
        event: dict[str, object],
        features: dict[str, object],
        scores: dict[str, float],
        agents_used: list[str],
        final_decision: str,
        validation: str,
        model_version: str,
        policy_version: str,
        reusability_score: float,
        ttl_seconds: int = 3600,
    ) -> None:
        fingerprint = self.fingerprint_engine.generate(
            event=event,
            features=features,
            graph_context={"source": event.get("source"), "target": event.get("target")},
            trust_context={agent_id: self.trust_registry.get_profile(agent_id).base_trust for agent_id in agents_used},
        )
        self.case_memory_store.store_case(
            fingerprint=fingerprint.fingerprint,
            fingerprint_version=fingerprint.version,
            fingerprint_material=fingerprint.material,
            scores=scores,
            agents_used=agents_used,
            final_decision=final_decision,
            validation=validation,
            model_version=model_version,
            policy_version=policy_version,
            reusability_score=reusability_score,
            ttl_seconds=ttl_seconds,
            metadata={"event_id": event.get("event_id")},
        )

    def retrain_models_if_needed(
        self,
        *,
        agents: dict[str, object],
        episode: int,
        min_interval: int = 3,
    ) -> bool:
        frame = self.memory.frame()
        drift_detected = any(self.detect_agent_drift(agent_id) >= 0.18 for agent_id in agents if agent_id != "sentinel")
        should_retrain = episode > 0 and episode % min_interval == 0 or drift_detected
        if should_retrain and not frame.empty:
            for agent_id, agent in agents.items():
                if agent_id == "sentinel" or not hasattr(agent, "update_model"):
                    continue
                agent.update_model(frame.tail(300))
        if should_retrain and self.sentinel_rl is not None and hasattr(self.sentinel_rl, "epsilon"):
            self.sentinel_rl.epsilon = max(self.sentinel_rl.epsilon_min, self.sentinel_rl.epsilon * 0.98)
        return should_retrain

    def retrain_models(
        self,
        *,
        agents: dict[str, object],
        episode: int,
        min_interval: int = 3,
    ) -> bool:
        return self.retrain_models_if_needed(agents=agents, episode=episode, min_interval=min_interval)
