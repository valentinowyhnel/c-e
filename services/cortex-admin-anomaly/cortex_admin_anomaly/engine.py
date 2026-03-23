from __future__ import annotations

from collections import Counter, defaultdict

from .models import AdminActionEvent, AdminCompromiseSignal, AdminSessionRequest


class AdminBehaviorStore:
    def __init__(self) -> None:
        self._actions_by_admin: dict[str, list[AdminActionEvent]] = defaultdict(list)

    def clear(self) -> None:
        self._actions_by_admin.clear()

    def ingest(self, event: AdminActionEvent) -> None:
        self._actions_by_admin[event.admin_id].append(event)

    def admin_behavior_profile(self, admin_id: str) -> dict[str, object]:
        events = self._actions_by_admin.get(admin_id, [])
        actions = Counter(event.action for event in events)
        resource_families = Counter(event.resource_family for event in events)
        return {
            "action_counts": actions,
            "resource_families": resource_families,
            "history_size": len(events),
        }

    def action_chain_rarity(self, admin_id: str, actions: list[AdminActionEvent]) -> float:
        profile = self.admin_behavior_profile(admin_id)
        counts: Counter[str] = profile["action_counts"]  # type: ignore[assignment]
        history_size: int = profile["history_size"]  # type: ignore[assignment]
        if history_size == 0:
            return 80.0
        rare = sum(1 for event in actions if counts.get(event.action, 0) <= 1)
        return min(100.0, round((rare / max(1, len(actions))) * 100.0, 2))

    def causal_break_score(self, admin_id: str, actions: list[AdminActionEvent]) -> float:
        profile = self.admin_behavior_profile(admin_id)
        families: Counter[str] = profile["resource_families"]  # type: ignore[assignment]
        unusual_family = any(families.get(event.resource_family, 0) == 0 for event in actions)
        abrupt_escalation = any(
            current.privilege_level == "domain_admin" and previous.privilege_level != "domain_admin"
            for previous, current in zip(actions, actions[1:])
        )
        score = 0.0
        if unusual_family:
            score += 45.0
        if abrupt_escalation:
            score += 35.0
        if actions and actions[0].action in {"dump_secrets", "rotate_breakglass"}:
            score += 20.0
        return min(100.0, round(score, 2))

    def admin_session_escalation_detector(self, admin_id: str, actions: list[AdminActionEvent], trace_id: str, correlation_id: str | None) -> AdminCompromiseSignal:
        profile = self.admin_behavior_profile(admin_id)
        history_size: int = profile["history_size"]  # type: ignore[assignment]
        profile_score = max(0.0, min(100.0, round(100.0 - min(80.0, history_size * 2.0), 2)))
        rarity = self.action_chain_rarity(admin_id, actions)
        causal_break = self.causal_break_score(admin_id, actions)
        escalation = min(100.0, round(profile_score * 0.2 + rarity * 0.35 + causal_break * 0.45, 2))
        evidence: list[str] = []
        if rarity >= 60:
            evidence.append("sequence never seen in historical admin profile")
        if causal_break >= 45:
            evidence.append("causal chain deviates from baseline")
        if any(event.resource_family == "crown-jewel-secrets" for event in actions):
            evidence.append("resource family unusual for this admin")
        confidence = min(0.95, round(0.42 + 0.08 * len(evidence), 2))
        return AdminCompromiseSignal(
            admin_id=admin_id,
            admin_behavior_profile_score=profile_score,
            action_chain_rarity=rarity,
            causal_break_score=causal_break,
            admin_session_escalation_score=escalation,
            confidence=confidence,
            evidence=evidence,
            trace_id=trace_id,
            correlation_id=correlation_id,
        )
