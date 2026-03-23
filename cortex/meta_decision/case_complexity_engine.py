from __future__ import annotations

from dataclasses import dataclass


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


@dataclass
class ComplexityAssessment:
    complexity_level: str
    score: float
    triggers: dict[str, bool]
    deep_analysis_required: bool


class CaseComplexityEngine:
    def assess(
        self,
        *,
        novelty_score: float,
        graph_depth: float,
        temporal_span: float,
        conflict_score: float,
        criticality: float,
    ) -> ComplexityAssessment:
        score = _clamp(
            0.24 * novelty_score
            + 0.18 * graph_depth
            + 0.16 * temporal_span
            + 0.20 * conflict_score
            + 0.22 * criticality
        )
        triggers = {
            "high_conflict": conflict_score >= 0.55,
            "high_novelty": novelty_score >= 0.7,
            "critical_asset": criticality >= 0.75,
            "broad_graph_impact": graph_depth >= 0.7,
        }
        if score < 0.35:
            level = "FAST_PATH"
        elif score < 0.65:
            level = "GUARDED_PATH"
        else:
            level = "DEEP_PATH"
        deep_analysis_required = level == "DEEP_PATH" or any(triggers.values())
        return ComplexityAssessment(
            complexity_level=level,
            score=score,
            triggers=triggers,
            deep_analysis_required=deep_analysis_required,
        )
