from __future__ import annotations

from dataclasses import dataclass

from app.models import ModelSnapshot


@dataclass(slots=True)
class PromotionDecision:
    approved: bool
    mode: str
    reasons: list[str]


class PromotionManager:
    def __init__(self, patience: int = 3) -> None:
        self.patience = patience
        self._stable_rounds = 0

    def evaluate(
        self,
        champion: ModelSnapshot | None,
        challenger: ModelSnapshot,
        metrics: dict[str, float],
        signed_approval: bool,
        poisoning_suspected: bool,
        drift_hard: bool,
    ) -> PromotionDecision:
        reasons: list[str] = []
        if not signed_approval:
            reasons.append("missing_signed_approval")
        if poisoning_suspected:
            reasons.append("poisoning_suspected")
        if drift_hard:
            reasons.append("hard_drift_active")
        if metrics.get("shadow_vs_champion_delta", -1.0) <= 0:
            reasons.append("no_robust_gain")
        if metrics.get("baseline_stability_score", 0.0) < 0.6:
            reasons.append("baseline_unstable")
        if reasons:
            self._stable_rounds = 0
            return PromotionDecision(approved=False, mode="shadow", reasons=reasons)
        self._stable_rounds += 1
        if self._stable_rounds < self.patience:
            return PromotionDecision(approved=False, mode="canary", reasons=["patience_not_met"])
        return PromotionDecision(approved=True, mode="promote", reasons=["signed_robust_gain"])

