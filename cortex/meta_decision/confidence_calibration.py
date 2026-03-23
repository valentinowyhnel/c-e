from __future__ import annotations


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


class ConfidenceCalibrationLayer:
    def calibrate(self, raw_scores: dict[str, float], trust_matrix: dict[str, dict[str, float]]) -> dict[str, float]:
        calibrated: dict[str, float] = {}
        for agent_id, score in raw_scores.items():
            criteria = trust_matrix.get(agent_id, {})
            uncertainty = float(criteria.get("uncertainty", 0.0))
            historical_accuracy = float(criteria.get("historical_accuracy", 0.5))
            overconfidence_penalty = 0.22 * uncertainty + 0.15 * max(0.0, score - historical_accuracy)
            calibrated[agent_id] = _clamp(score - overconfidence_penalty)
        return calibrated
