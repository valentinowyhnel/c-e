from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOTS = [
    ROOT / "services" / "cortex-campaign-memory",
    ROOT / "services" / "cortex-priority-engine",
    ROOT / "services" / "cortex-policy-engine",
    ROOT / "shared" / "cortex-core",
]
for root in SERVICE_ROOTS:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from cortex_campaign_memory.models import CampaignEventFingerprint  # noqa: E402
from cortex_campaign_memory.store import CampaignMemoryStore  # noqa: E402
from cortex_core.contracts import (  # noqa: E402
    ActionClass,
    DependencyHealthSnapshot,
    DependencyState,
    ExecutionGuardrails,
    RiskEnvelope,
)
from cortex_policy_engine.engine import PolicyEngine  # noqa: E402
from cortex_priority_engine.engine import compute_priority  # noqa: E402
from cortex_priority_engine.models import PriorityEvaluationRequest  # noqa: E402


def test_low_and_slow_campaign_triggers_deep_path_and_policy_block_before_crown_jewel() -> None:
    store = CampaignMemoryStore()
    now = time.time()
    for offset_days, weak_signal, novelty, anomaly in [
        (29, 24, 58, 44),
        (21, 27, 62, 47),
        (14, 31, 64, 49),
        (7, 34, 66, 52),
        (2, 38, 69, 55),
    ]:
        store.store_event_fingerprint(
            CampaignEventFingerprint(
                identity_id="admin-apt",
                path_id="unknown-edge-chain",
                resource_family="crown-jewel-secrets",
                weak_signal_score=weak_signal,
                novelty_score=novelty,
                anomaly_score=anomaly,
                timestamp=now - offset_days * 24 * 3600,
                trace_id="trace-e2e-low-slow",
            )
        )

    campaign_signal = store.campaign_likelihood_score(
        identity_id="admin-apt",
        path_id="unknown-edge-chain",
        resource_family="crown-jewel-secrets",
        trace_id="trace-e2e-low-slow",
    )
    assert campaign_signal.campaign_likelihood_score >= 75

    priority_signal = compute_priority(
        PriorityEvaluationRequest(
            entity_id="admin-apt",
            anomaly_score=57,
            novelty_score=66,
            trust_score=39,
            graph_expansion=61,
            asset_criticality=92,
            campaign_likelihood=campaign_signal.campaign_likelihood_score,
            persistence_likelihood=81,
            trace_id="trace-e2e-low-slow",
        )
    )
    assert priority_signal.route in {"deep_graph_reasoning", "sentinel_immediate_attention"}

    policy = PolicyEngine()
    decision = policy.evaluate(
        RiskEnvelope(
            entity_id="admin-apt",
            entity_type="identity",
            action="execute_quarantine",
            action_class=ActionClass.EXECUTE_WITH_APPROVAL,
            trust_score=39,
            threat_level=4,
            evidence_count=5,
            strong_signal_count=3,
            distinct_sources=3,
            blast_radius=32,
            crown_jewels_exposed=True,
            criticality="critical",
            scopes=["admin:write"],
            environment="preprod",
            dependencies=DependencyHealthSnapshot(
                nats=DependencyState.HEALTHY,
                approval=DependencyState.HEALTHY,
                sentinel=DependencyState.HEALTHY,
                neo4j=DependencyState.HEALTHY,
                bloodhound=DependencyState.HEALTHY,
            ),
        ),
        ExecutionGuardrails(
            action_class=ActionClass.EXECUTE_WITH_APPROVAL,
            approval_required=True,
            forensic_required=True,
            min_sources=2,
        ),
        "local_quarantine",
    )
    assert decision.decision.value == "approval_required"
    assert decision.forensic_required is True
