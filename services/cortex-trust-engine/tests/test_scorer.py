from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = Path(__file__).resolve().parents[3] / "shared" / "cortex-core"
for root in (ROOT, CORE_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from cortex_trust_engine.models import TrustDecision
from cortex_trust_engine.scorer import compute_score, make_decision, response_eligibility_for, score_evidences
from cortex_core.contracts import (
    ActionClass,
    DependencyHealthSnapshot,
    DependencyState,
    ResponseEligibility,
    RiskEnvelope,
    SecurityEvidence,
)


def test_compute_score_caps_at_bounds() -> None:
    assert compute_score(95, ["mfa_verified"]) == 100
    assert compute_score(5, ["impossible_travel"]) == 0


def test_make_decision_thresholds() -> None:
    assert make_decision(85) is TrustDecision.ALLOW
    assert make_decision(65) is TrustDecision.MONITOR
    assert make_decision(45) is TrustDecision.RESTRICTED
    assert make_decision(25) is TrustDecision.DENY
    assert make_decision(10) is TrustDecision.REVOKE


def test_multi_source_high_severity_drops_score() -> None:
    evidences = [
        SecurityEvidence(
            entity_id="machine-1",
            source="falco_rule",
            signal_type="cred_dump",
            severity=0.9,
            confidence=0.9,
            timestamp=time.time() - 5,
            ttl=300,
        ),
        SecurityEvidence(
            entity_id="machine-1",
            source="auditd_exec",
            signal_type="suspicious_exec",
            severity=0.8,
            confidence=0.8,
            timestamp=time.time() - 10,
            ttl=300,
        ),
    ]
    score, distinct_sources, strong_signals = score_evidences(85.0, evidences, criticality="critical")
    assert score < 70
    assert distinct_sources == 2
    assert strong_signals == 2


def test_single_weak_signal_is_monitor_only() -> None:
    envelope = RiskEnvelope(
        entity_id="machine-1",
        entity_type="machine",
        action="prepare_irreversible_containment",
        action_class=ActionClass.IRREVERSIBLE,
        trust_score=48.0,
        threat_level=2,
        evidence_count=1,
        strong_signal_count=1,
        distinct_sources=1,
        blast_radius=3,
        dependencies=DependencyHealthSnapshot(
            nats=DependencyState.HEALTHY,
            approval=DependencyState.HEALTHY,
            sentinel=DependencyState.HEALTHY,
        ),
    )
    assert response_eligibility_for(envelope) is ResponseEligibility.MONITOR_ONLY


def test_approval_outage_prevents_autonomous_irreversible_eligibility() -> None:
    envelope = RiskEnvelope(
        entity_id="machine-1",
        entity_type="machine",
        action="execute_irreversible_containment",
        action_class=ActionClass.IRREVERSIBLE,
        trust_score=5.0,
        threat_level=5,
        evidence_count=3,
        strong_signal_count=3,
        distinct_sources=3,
        blast_radius=10,
        dependencies=DependencyHealthSnapshot(
            nats=DependencyState.HEALTHY,
            approval=DependencyState.UNAVAILABLE,
            sentinel=DependencyState.HEALTHY,
        ),
    )
    assert response_eligibility_for(envelope) is ResponseEligibility.REVERSIBLE_ONLY
