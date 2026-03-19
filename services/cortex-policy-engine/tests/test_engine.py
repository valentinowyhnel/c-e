from __future__ import annotations

import sys
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[3] / "shared" / "cortex-core"
SERVICE_ROOT = Path(__file__).resolve().parents[1]
for root in (CORE_ROOT, SERVICE_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from cortex_core.contracts import (  # noqa: E402
    ActionClass,
    CapabilityMaturity,
    DependencyHealthSnapshot,
    DependencyState,
    ExecutionDecision,
    ExecutionGuardrails,
    RiskEnvelope,
)
from cortex_policy_engine.engine import PolicyEngine  # noqa: E402


def make_envelope(**overrides):
    base = RiskEnvelope(
        entity_id="node-1",
        entity_type="machine",
        action="prepare_quarantine",
        action_class=ActionClass.PREPARE_ONLY,
        trust_score=40,
        threat_level=4,
        evidence_count=3,
        strong_signal_count=2,
        distinct_sources=2,
        blast_radius=3,
        crown_jewels_exposed=False,
        criticality="normal",
        scopes=["admin:write"],
        environment="preprod",
        dependencies=DependencyHealthSnapshot(
            nats=DependencyState.HEALTHY,
            approval=DependencyState.HEALTHY,
            sentinel=DependencyState.HEALTHY,
            vault=DependencyState.HEALTHY,
            neo4j=DependencyState.HEALTHY,
            bloodhound=DependencyState.HEALTHY,
            external_llm=DependencyState.HEALTHY,
        ),
    )
    return base.model_copy(update=overrides)


def test_prepare_only_respected():
    engine = PolicyEngine()
    decision = engine.evaluate(
        make_envelope(),
        ExecutionGuardrails(action_class=ActionClass.PREPARE_ONLY),
        "local_quarantine",
    )
    assert decision.decision == ExecutionDecision.PREPARE_ONLY


def test_irreversible_blocked_on_single_weak_signal():
    engine = PolicyEngine()
    decision = engine.evaluate(
        make_envelope(
            action="execute_irreversible_containment",
            action_class=ActionClass.IRREVERSIBLE,
            strong_signal_count=1,
            distinct_sources=1,
            environment="dev",
        ),
        ExecutionGuardrails(
            action_class=ActionClass.IRREVERSIBLE,
            min_sources=2,
            forensic_required=True,
        ),
        "irreversible_containment",
    )
    assert decision.decision == ExecutionDecision.PREPARE_ONLY
    assert decision.forensic_required is True


def test_degraded_mode_blocks_irreversible():
    engine = PolicyEngine()
    decision = engine.evaluate(
        make_envelope(
            action="execute_irreversible_containment",
            action_class=ActionClass.IRREVERSIBLE,
            environment="dev",
            dependencies=DependencyHealthSnapshot(
                nats=DependencyState.UNAVAILABLE,
                approval=DependencyState.HEALTHY,
                sentinel=DependencyState.HEALTHY,
            ),
        ),
        ExecutionGuardrails(action_class=ActionClass.IRREVERSIBLE),
        "irreversible_containment",
    )
    assert decision.decision == ExecutionDecision.BLOCKED_DUE_TO_DEGRADED_MODE


def test_missing_admin_scope_denied():
    engine = PolicyEngine()
    decision = engine.evaluate(
        make_envelope(
            action="execute_quarantine",
            action_class=ActionClass.EXECUTE_WITH_APPROVAL,
            scopes=["read:graph"],
        ),
        ExecutionGuardrails(action_class=ActionClass.EXECUTE_WITH_APPROVAL, approval_required=True),
        "local_quarantine",
    )
    assert decision.decision == ExecutionDecision.DENIED


def test_experimental_blocked_in_prod():
    engine = PolicyEngine()
    decision = engine.evaluate(
        make_envelope(environment="prod"),
        ExecutionGuardrails(action_class=ActionClass.PREPARE_ONLY, block_if_maturity_below=CapabilityMaturity.PRODUCTION_READY),
        "decision_committee",
    )
    assert decision.decision == ExecutionDecision.DENIED
