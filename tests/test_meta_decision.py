from __future__ import annotations

from cortex.meta_decision import (
    AgentTrustRegistry,
    AnalysisFingerprintEngine,
    AnalysisReuseOrchestrator,
    CaseMemoryStore,
    DecisionMemoryLinker,
    DecisionTrustEngine,
    MetaDecisionAgent,
)


def build_agent() -> MetaDecisionAgent:
    registry = AgentTrustRegistry()
    registry.register_agent("anomaly", specialties={"anomaly_score": 0.9}, base_trust=0.7)
    registry.register_agent("graph", specialties={"graph_score": 0.85}, base_trust=0.65)
    registry.register_agent("trust", specialties={"trust_score": 0.95}, base_trust=0.72)
    return MetaDecisionAgent(
        decision_trust_engine=DecisionTrustEngine(registry),
        decision_memory_linker=DecisionMemoryLinker(
            fingerprint_engine=AnalysisFingerprintEngine(),
            case_memory_store=CaseMemoryStore(),
            reuse_orchestrator=AnalysisReuseOrchestrator(),
        ),
    )


def test_meta_decision_fast_path_does_not_trigger_deep_analysis() -> None:
    agent = build_agent()
    event = {
        "event_id": "evt-1",
        "timestamp": 1,
        "novelty_score": 0.22,
        "graph_score": 0.25,
        "temporal_score": 0.18,
        "asset_criticality": 0.2,
        "blast_radius": 0.15,
        "metadata": {"crown_jewel": False},
    }
    messages = [
        {"sender": "anomaly", "risk_signal": 0.3, "runtime_trust": 0.8, "uncertainty": 0.2, "data_quality": 0.8, "reasoning_quality": 0.7, "specialty": "anomaly_score"},
        {"sender": "graph", "risk_signal": 0.28, "runtime_trust": 0.78, "uncertainty": 0.22, "data_quality": 0.76, "reasoning_quality": 0.7, "specialty": "graph_score"},
        {"sender": "trust", "risk_signal": 0.26, "runtime_trust": 0.82, "uncertainty": 0.25, "data_quality": 0.8, "reasoning_quality": 0.72, "specialty": "trust_score"},
    ]
    result = agent.evaluate(event=event, agent_messages=messages)
    assert result.deep_analysis_triggered is False
    assert result.conflict_score < 0.1
    assert result.weighted_scores["aggregate_risk"] > 0.0
    assert result.audit_log["complexity_level"] == "FAST_PATH"
    assert result.audit_log["reuse_decision"] == "NO_REUSE"


def test_meta_decision_triggers_deep_analysis_on_conflict_and_criticality() -> None:
    agent = build_agent()
    event = {
        "event_id": "evt-2",
        "timestamp": 2,
        "novelty_score": 0.84,
        "graph_score": 0.82,
        "temporal_score": 0.71,
        "asset_criticality": 0.95,
        "blast_radius": 0.88,
        "metadata": {"crown_jewel": True},
    }
    messages = [
        {"sender": "anomaly", "risk_signal": 0.92, "runtime_trust": 0.5, "uncertainty": 0.45, "data_quality": 0.7, "reasoning_quality": 0.6, "specialty": "anomaly_score"},
        {"sender": "graph", "risk_signal": 0.12, "runtime_trust": 0.48, "uncertainty": 0.52, "data_quality": 0.65, "reasoning_quality": 0.55, "specialty": "graph_score"},
        {"sender": "trust", "risk_signal": 0.86, "runtime_trust": 0.51, "uncertainty": 0.4, "data_quality": 0.7, "reasoning_quality": 0.65, "specialty": "trust_score"},
    ]
    result = agent.evaluate(event=event, agent_messages=messages)
    assert result.deep_analysis_triggered is True
    assert result.conflict_score > 0.5
    assert result.deep_analysis_requests
    assert "critical_asset" in result.audit_log["deep_analysis_reasons"]


def test_meta_decision_reuses_prior_analysis_when_case_matches() -> None:
    registry = AgentTrustRegistry()
    registry.register_agent("anomaly", specialties={"anomaly_score": 0.9}, base_trust=0.7)
    registry.register_agent("graph", specialties={"graph_score": 0.85}, base_trust=0.65)
    registry.register_agent("trust", specialties={"trust_score": 0.95}, base_trust=0.72)
    memory = CaseMemoryStore()
    linker = DecisionMemoryLinker(
        fingerprint_engine=AnalysisFingerprintEngine(),
        case_memory_store=memory,
        reuse_orchestrator=AnalysisReuseOrchestrator(),
    )
    agent = MetaDecisionAgent(
        decision_trust_engine=DecisionTrustEngine(registry),
        decision_memory_linker=linker,
    )
    event = {
        "event_id": "evt-3",
        "timestamp": 3,
        "scenario": "credential_stuffing",
        "phase": "execution",
        "source": "workstation-a",
        "target": "app-1",
        "novelty_score": 0.12,
        "graph_score": 0.22,
        "temporal_score": 0.18,
        "asset_criticality": 0.2,
        "blast_radius": 0.1,
        "metadata": {"crown_jewel": False},
    }
    prior_fingerprint = linker.fingerprint_engine.generate(
        event=event,
        features={"graph": 0.2},
        graph_context={"source": "workstation-a", "target": "app-1"},
        trust_context={"anomaly": 0.7},
    )
    memory.store_case(
        fingerprint=prior_fingerprint.fingerprint,
        fingerprint_version=prior_fingerprint.version,
        fingerprint_material=prior_fingerprint.material,
        scores={"aggregate_risk": 0.61},
        agents_used=["anomaly", "graph"],
        final_decision="INVESTIGATE",
        validation="confirmed",
        model_version="anomaly:default:v1|graph:default:v1|hunter:default:v1|trust:default:v1",
        policy_version="opa:v1",
        reusability_score=0.92,
        metadata={"event_id": "evt-prev"},
    )
    result = agent.evaluate(
        event=event,
        agent_messages=[
            {"sender": "anomaly", "risk_signal": 0.45, "runtime_trust": 0.8, "uncertainty": 0.2, "data_quality": 0.8, "reasoning_quality": 0.7, "specialty": "anomaly_score"},
            {"sender": "graph", "risk_signal": 0.42, "runtime_trust": 0.79, "uncertainty": 0.24, "data_quality": 0.78, "reasoning_quality": 0.68, "specialty": "graph_score"},
        ],
        model_scores={"graph": 0.2},
        identity_context={"source": "workstation-a", "target": "app-1"},
        graph_context={"source": "workstation-a", "target": "app-1"},
        policy_version="opa:v1",
        model_versions={name: "default:v1" for name in ["anomaly", "graph", "hunter", "trust"]},
    )
    assert result.audit_log["reuse_decision"] in {"FULL_REUSE", "PARTIAL_REUSE"}
    assert result.reuse_context
    assert result.weighted_scores["aggregate_risk"] > 0.45
