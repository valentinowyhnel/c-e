from __future__ import annotations

from math import sqrt

from app.models import LearningGuardDecision, LocalUpdate


class LearningGuard:
    def __init__(self) -> None:
        self._seen_nonces: set[str] = set()

    def evaluate(
        self,
        update: LocalUpdate,
        machine_compromised: bool,
        labels_inconsistent: bool,
        corroborated: bool,
        reference_degradation: float,
    ) -> LearningGuardDecision:
        reasons: list[str] = []
        confidence_penalty = 0.0
        norm = sqrt(sum(value * value for value in update.delta.values()))
        if update.replay_nonce in self._seen_nonces:
            reasons.append("replay_detected")
        if machine_compromised:
            reasons.append("machine_compromised")
        if labels_inconsistent:
            reasons.append("labels_inconsistent")
            confidence_penalty += 0.2
        if not corroborated:
            reasons.append("missing_corroboration")
            confidence_penalty += 0.15
        if norm > 3.0:
            reasons.append("delta_out_of_envelope")
            confidence_penalty += 0.25
        if update.suspicion_score > 0.6:
            reasons.append("self_suspicion_high")
            confidence_penalty += 0.15
        if reference_degradation > 0.05:
            reasons.append("roni_failed")
        quarantined = any(reason in {"machine_compromised", "roni_failed", "replay_detected"} for reason in reasons)
        accepted = not quarantined and "delta_out_of_envelope" not in reasons
        self._seen_nonces.add(update.replay_nonce)
        return LearningGuardDecision(
            accepted=accepted,
            quarantined=quarantined,
            confidence_penalty=round(confidence_penalty, 4),
            reasons=reasons,
        )
