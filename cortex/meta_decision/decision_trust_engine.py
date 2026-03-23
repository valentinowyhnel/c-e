from __future__ import annotations

from dataclasses import dataclass

from .agent_trust_registry import AgentProfile, AgentTrustRegistry


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


@dataclass
class TrustComputation:
    agent_case_trust: dict[str, float]
    trust_matrix: dict[str, dict[str, float]]


class DecisionTrustEngine:
    def __init__(self, registry: AgentTrustRegistry) -> None:
        self.registry = registry
        self.weights = {
            "base_trust": 0.18,
            "runtime_trust": 0.16,
            "case_trust": 0.18,
            "historical_accuracy": 0.16,
            "uncertainty": -0.12,
            "data_quality": 0.14,
            "reasoning_quality": 0.18,
        }

    def _resolve_profile(self, agent_id: str, specialty: str | None) -> tuple[AgentProfile, dict[str, float]]:
        profile = self.registry.get_profile(agent_id)
        case_trust = self.registry.case_trust_for(agent_id, specialty)
        historical_accuracy = profile.historical_accuracy.get(specialty or "global", case_trust)
        criteria = {
            "base_trust": _clamp(profile.base_trust),
            "runtime_trust": _clamp(profile.runtime_trust),
            "case_trust": _clamp(case_trust),
            "historical_accuracy": _clamp(historical_accuracy),
        }
        return profile, criteria

    def compute_agent_trust(
        self,
        agent_id: str,
        *,
        specialty: str | None = None,
        runtime_trust: float | None = None,
        uncertainty: float = 0.0,
        data_quality: float = 0.5,
        reasoning_quality: float = 0.5,
    ) -> tuple[float, dict[str, float]]:
        _profile, criteria = self._resolve_profile(agent_id, specialty)
        if runtime_trust is not None:
            criteria["runtime_trust"] = _clamp(runtime_trust)
            self.registry.update_runtime_trust(agent_id, runtime_trust)
        criteria["uncertainty"] = _clamp(uncertainty)
        criteria["data_quality"] = _clamp(data_quality)
        criteria["reasoning_quality"] = _clamp(reasoning_quality)
        trust = 0.0
        for name, value in criteria.items():
            trust += self.weights[name] * value
        return _clamp(trust), criteria

    def compute_batch(self, agent_inputs: list[dict[str, object]]) -> TrustComputation:
        scores: dict[str, float] = {}
        matrix: dict[str, dict[str, float]] = {}
        for item in agent_inputs:
            agent_id = str(item["agent_id"])
            trust, criteria = self.compute_agent_trust(
                agent_id,
                specialty=item.get("specialty"),
                runtime_trust=float(item.get("runtime_trust", self.registry.get_profile(agent_id).runtime_trust)),
                uncertainty=float(item.get("uncertainty", 0.0)),
                data_quality=float(item.get("data_quality", 0.5)),
                reasoning_quality=float(item.get("reasoning_quality", 0.5)),
            )
            scores[agent_id] = trust
            matrix[agent_id] = criteria
        return TrustComputation(agent_case_trust=scores, trust_matrix=matrix)
