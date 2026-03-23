from __future__ import annotations

from dataclasses import dataclass

from .case_memory_store import MemoryCase


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


@dataclass
class ReuseDecision:
    reuse_decision: str
    reuse_confidence: float
    agents_to_bypass: list[str]
    agents_to_recheck: list[str]
    rationale: list[str]
    matched_case: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "reuse_decision": self.reuse_decision,
            "reuse_confidence": self.reuse_confidence,
            "agents_to_bypass": list(self.agents_to_bypass),
            "agents_to_recheck": list(self.agents_to_recheck),
            "rationale": list(self.rationale),
            "matched_case": dict(self.matched_case) if self.matched_case else None,
        }


class AnalysisReuseOrchestrator:
    def decide(
        self,
        *,
        fingerprint: str,
        matching_cases: list[dict[str, object]],
        novelty_score: float,
        criticality: float,
        policy_version: str,
        model_versions: dict[str, str],
        event_flags: dict[str, bool] | None = None,
    ) -> ReuseDecision:
        flags = event_flags or {}
        rationale: list[str] = []
        if any(flags.get(name, False) for name in ("zero_day_possible", "admin_compromise", "insider", "crown_jewel")):
            rationale.append("reuse_blocked_by_critical_flag")
            return ReuseDecision("NO_REUSE", 0.0, [], [], rationale)
        if not matching_cases:
            rationale.append("no_matching_case")
            return ReuseDecision("NO_REUSE", 0.0, [], [], rationale)

        best_match = matching_cases[0]
        case: MemoryCase = best_match["case"]
        similarity = float(best_match["similarity"])
        version_signature = "|".join(f"{name}:{model_versions[name]}" for name in sorted(model_versions))
        version_match = case.policy_version == policy_version and case.model_version == version_signature
        confidence = _clamp(0.45 * similarity + 0.35 * case.reusability_score + 0.20 * (1.0 - novelty_score))
        if version_match:
            confidence = _clamp(confidence + 0.08)
        if criticality >= 0.8:
            confidence = _clamp(confidence - 0.2)
            rationale.append("criticality_penalty")
        if similarity >= 0.96 and confidence >= 0.8 and version_match:
            rationale.append("exact_reusable_case")
            return ReuseDecision(
                "FULL_REUSE",
                confidence,
                list(case.agents_used),
                [],
                rationale,
                matched_case=case.to_dict(),
            )
        if similarity >= 0.8 and confidence >= 0.55:
            rationale.append("partial_recheck_required")
            recheck = list(case.agents_used[:1]) if case.agents_used else []
            bypass = [agent for agent in case.agents_used if agent not in recheck]
            return ReuseDecision(
                "PARTIAL_REUSE",
                confidence,
                bypass,
                recheck,
                rationale,
                matched_case=case.to_dict(),
            )
        rationale.append("reuse_confidence_too_low")
        return ReuseDecision("NO_REUSE", confidence, [], list(case.agents_used), rationale, matched_case=case.to_dict())
