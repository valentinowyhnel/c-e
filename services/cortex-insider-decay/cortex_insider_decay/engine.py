from __future__ import annotations

from collections import defaultdict

from .models import InsiderDecaySignal, InsiderEvaluationRequest, InsiderEvent


class InsiderDecayStore:
    def __init__(self) -> None:
        self._history: dict[str, list[InsiderEvent]] = defaultdict(list)

    def clear(self) -> None:
        self._history.clear()

    def ingest(self, event: InsiderEvent) -> None:
        self._history[event.identity_id].append(event)

    def role_misalignment_score(self, events: list[InsiderEvent]) -> float:
        mismatches = sum(1 for event in events if event.role != event.expected_role)
        return min(100.0, round((mismatches / max(1, len(events))) * 100.0, 2))

    def sensitive_access_without_context(self, events: list[InsiderEvent]) -> float:
        score = 0.0
        for event in events:
            if event.data_criticality in {"high", "critical"} and not event.justification_present:
                score += 25.0
            if event.hour_utc < 6 or event.hour_utc > 21:
                score += 10.0
            if event.organization_context == "off_process":
                score += 15.0
        return min(100.0, round(score, 2))

    def cumulative_trust_decay(self, identity_id: str, events: list[InsiderEvent]) -> float:
        history = self._history.get(identity_id, [])
        window = history[-20:] + events
        role_score = self.role_misalignment_score(window)
        context_score = self.sensitive_access_without_context(window)
        repeated = min(25.0, max(0, len(window) - 2) * 3.0)
        return min(100.0, round(role_score * 0.35 + context_score * 0.45 + repeated, 2))

    def trust_decay_recovery_if_legit(self, events: list[InsiderEvent]) -> float:
        recovery = sum(12.0 for event in events if event.legit_recovery or event.justification_present)
        return min(40.0, round(recovery, 2))

    def evaluate(self, req: InsiderEvaluationRequest) -> InsiderDecaySignal:
        role_score = self.role_misalignment_score(req.events)
        context_score = self.sensitive_access_without_context(req.events)
        cumulative = self.cumulative_trust_decay(req.identity_id, req.events)
        recovery = self.trust_decay_recovery_if_legit(req.events)
        net_decay = max(0.0, round(cumulative - recovery, 2))
        evidence: list[str] = []
        if role_score >= 40:
            evidence.append("role alignment deviates from expected baseline")
        if context_score >= 35:
            evidence.append("sensitive access lacks business context")
        if net_decay >= 60:
            evidence.append("repeated subtle deviations accumulate over time")
        confidence = min(0.94, round(0.4 + 0.08 * len(evidence), 2))
        return InsiderDecaySignal(
            identity_id=req.identity_id,
            role_misalignment_score=role_score,
            sensitive_access_without_context_score=context_score,
            cumulative_trust_decay=net_decay,
            trust_decay_recovery=recovery,
            confidence=confidence,
            evidence=evidence,
            trace_id=req.trace_id,
            correlation_id=req.correlation_id,
        )
