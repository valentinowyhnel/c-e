from __future__ import annotations

import time

from cortex_trust_engine.models import ThreatLevel, TrustDecision

from cortex_core.contracts import (  # noqa: E402
    DependencyState,
    ResponseEligibility,
    RiskEnvelope,
    SecurityEvidence,
)

POSITIVE_FACTORS = {
    "mfa_verified": 15,
    "passkey_used": 12,
    "device_compliant": 10,
    "known_network": 8,
    "normal_working_hours": 5,
    "recent_successful_auth": 5,
    "long_term_account": 3,
    "low_privilege_requested": 3,
}

NEGATIVE_FACTORS = {
    "new_device": -20,
    "impossible_travel": -40,
    "failed_mfa_attempts": -15,
    "anomalous_api_pattern": -10,
    "privilege_escalation": -25,
    "off_hours_access": -8,
    "vpn_or_tor": -10,
    "high_risk_resource_access": -5,
    "agent_behavioral_deviation": -15,
    "stale_credentials": -8,
    "unusual_volume": -12,
}

SOURCE_TRUST = {
    "falco_rule": 0.9,
    "auditd_exec": 0.85,
    "auditd_connect": 0.8,
    "psutil_process": 0.65,
    "bloodhound": 0.8,
    "mcp": 0.6,
}

CRITICALITY_AMPLIFIER = {
    "normal": 1.0,
    "high": 1.25,
    "critical": 1.5,
}


def compute_score(base_score: int, factors: list[str]) -> int:
    score = base_score
    for factor in factors:
        score += POSITIVE_FACTORS.get(factor, 0)
        score += NEGATIVE_FACTORS.get(factor, 0)
    return max(0, min(100, score))


def score_evidences(base_score: float, evidences: list[SecurityEvidence], criticality: str = "normal") -> tuple[float, int, int]:
    score = base_score
    distinct_sources = {e.source for e in evidences}
    strong_signals = 0
    amplifier = CRITICALITY_AMPLIFIER.get(criticality, 1.0)
    now = time.time()
    for evidence in evidences:
        age = max(0.0, now - evidence.timestamp)
        freshness = max(0.1, 1.0 - (age / max(evidence.ttl, 1)))
        source_trust = SOURCE_TRUST.get(evidence.source, 0.5)
        impact = evidence.severity * min(evidence.confidence, source_trust) * freshness * amplifier * 12.0
        if evidence.severity >= 0.6:
            strong_signals += 1
            score -= impact
        else:
            score += impact * 0.2
    return max(0.0, min(100.0, round(score, 2))), len(distinct_sources), strong_signals


def make_decision(score: int) -> TrustDecision:
    if score >= 80:
        return TrustDecision.ALLOW
    if score >= 60:
        return TrustDecision.MONITOR
    if score >= 40:
        return TrustDecision.RESTRICTED
    if score >= 20:
        return TrustDecision.DENY
    return TrustDecision.REVOKE


def threat_level_for(score: float, strong_signals: int) -> ThreatLevel:
    if score < 20 or strong_signals >= 3:
        return ThreatLevel.CRITICAL
    if score < 40 or strong_signals >= 2:
        return ThreatLevel.HIGH
    if score < 70 or strong_signals >= 1:
        return ThreatLevel.ELEVATED
    return ThreatLevel.LOW


def response_eligibility_for(envelope: RiskEnvelope) -> ResponseEligibility:
    if envelope.dependencies.approval == DependencyState.UNAVAILABLE and envelope.action_class.value == "irreversible":
        return ResponseEligibility.REVERSIBLE_ONLY
    if envelope.strong_signal_count < 2:
        return ResponseEligibility.MONITOR_ONLY
    if envelope.crown_jewels_exposed or envelope.blast_radius > 25:
        return ResponseEligibility.APPROVAL_GATED
    if envelope.trust_score < 20 and envelope.distinct_sources >= 2:
        return ResponseEligibility.APPROVAL_GATED
    if envelope.trust_score < 40 and envelope.distinct_sources >= 2:
        return ResponseEligibility.REVERSIBLE_ONLY
    return ResponseEligibility.MONITOR_ONLY
