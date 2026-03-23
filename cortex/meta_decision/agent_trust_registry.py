from __future__ import annotations

from dataclasses import dataclass, field


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


@dataclass
class AgentProfile:
    agent_id: str
    capabilities: dict[str, float] = field(default_factory=dict)
    historical_accuracy: dict[str, float] = field(default_factory=dict)
    specialties: dict[str, float] = field(default_factory=dict)
    base_trust: float = 0.5
    drift_score: float = 0.0
    runtime_trust: float = 0.5
    performance_history: list[dict[str, float]] = field(default_factory=list)

    def snapshot(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "capabilities": dict(self.capabilities),
            "historical_accuracy": dict(self.historical_accuracy),
            "specialties": dict(self.specialties),
            "base_trust": self.base_trust,
            "drift_score": self.drift_score,
            "runtime_trust": self.runtime_trust,
            "performance_history": list(self.performance_history),
        }


class AgentTrustRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, AgentProfile] = {}

    def register_agent(
        self,
        agent_id: str,
        *,
        capabilities: dict[str, float] | None = None,
        specialties: dict[str, float] | None = None,
        base_trust: float = 0.5,
    ) -> AgentProfile:
        profile = self._profiles.get(agent_id)
        if profile is None:
            profile = AgentProfile(
                agent_id=agent_id,
                capabilities=capabilities or {},
                specialties=specialties or {},
                base_trust=_clamp(base_trust),
                runtime_trust=_clamp(base_trust),
            )
            self._profiles[agent_id] = profile
            return profile
        if capabilities:
            profile.capabilities.update(capabilities)
        if specialties:
            profile.specialties.update(specialties)
        profile.base_trust = _clamp(base_trust)
        return profile

    def get_profile(self, agent_id: str) -> AgentProfile:
        return self._profiles.setdefault(agent_id, AgentProfile(agent_id=agent_id))

    def update_runtime_trust(self, agent_id: str, runtime_trust: float) -> None:
        self.get_profile(agent_id).runtime_trust = _clamp(runtime_trust)

    def update_base_trust(self, agent_id: str, base_trust: float) -> None:
        self.get_profile(agent_id).base_trust = _clamp(base_trust)

    def update_historical_accuracy(self, agent_id: str, specialty: str, accuracy: float) -> None:
        self.get_profile(agent_id).historical_accuracy[specialty] = _clamp(accuracy)

    def update_drift(self, agent_id: str, drift_score: float) -> None:
        self.get_profile(agent_id).drift_score = _clamp(drift_score)

    def record_case_outcome(
        self,
        agent_id: str,
        *,
        specialty: str,
        correct: bool,
        confidence: float,
    ) -> None:
        profile = self.get_profile(agent_id)
        previous = profile.historical_accuracy.get(specialty, profile.base_trust)
        observed = 1.0 if correct else 0.0
        updated = 0.85 * previous + 0.15 * observed
        profile.historical_accuracy[specialty] = _clamp(updated)
        profile.performance_history.append(
            {
                "specialty": specialty,
                "correct": observed,
                "confidence": _clamp(confidence),
                "updated_accuracy": profile.historical_accuracy[specialty],
            }
        )

    def case_trust_for(self, agent_id: str, specialty: str | None = None) -> float:
        profile = self.get_profile(agent_id)
        if specialty and specialty in profile.specialties:
            specialty_weight = profile.specialties[specialty]
            specialty_accuracy = profile.historical_accuracy.get(specialty, profile.base_trust)
            return _clamp(0.6 * specialty_weight + 0.4 * specialty_accuracy)
        if profile.historical_accuracy:
            return _clamp(sum(profile.historical_accuracy.values()) / len(profile.historical_accuracy))
        return _clamp(profile.base_trust)

    def snapshot(self) -> dict[str, dict[str, object]]:
        return {agent_id: profile.snapshot() for agent_id, profile in self._profiles.items()}
