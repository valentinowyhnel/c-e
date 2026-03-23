from __future__ import annotations

import time

from cortex.mcp import MCPServer


def test_mcp_server_returns_structured_advisory_json() -> None:
    server = MCPServer()
    result = server.analyze(
        event={"event_id": "evt-mcp", "scenario": "lateral_movement", "novelty_score": 0.8, "asset_criticality": 0.6},
        agent_messages=[
            {"sender": "graph", "risk_signal": 0.8, "uncertainty": 0.2, "reasoning_quality": 0.7},
            {"sender": "trust", "risk_signal": 0.3, "uncertainty": 0.5, "reasoning_quality": 0.6},
        ],
        trust_scores={"graph": 0.74, "trust": 0.58},
        conflict_score=0.61,
        deep_analysis_reasons=["agent_conflict", "high_novelty"],
        memory_context={"reuse": {"reuse_decision": "NO_REUSE"}},
    )
    assert result.structured_output["advisory_only"] is True
    assert result.structured_output["hypotheses"]
    assert "final_decision" not in result.structured_output
    assert "final_decision" in result.audit_log["discarded_fields"]
    assert result.audit_log["output_schema"] == "json"
    assert result.audit_log["audit_required"] is True
    assert result.audit_log["llm_profile"]["name"] == "deep_reasoning"


def test_mcp_server_requires_event_id() -> None:
    server = MCPServer()
    result = server.analyze(
        event={"scenario": "missing_id"},
        agent_messages=[],
        trust_scores={},
        conflict_score=0.0,
        deep_analysis_reasons=[],
    )
    assert result.degraded_mode is True
    assert result.structured_output["explanation"] == "mcp_policy_guard_blocked"
    assert "missing_event_id" in result.audit_log["guard_reasons"]


def test_mcp_server_filters_forbidden_language() -> None:
    def fake_vllm(_model: str, _context: dict[str, object], _timeout_ms: int) -> dict[str, object]:
        return {
            "hypotheses": ["This may be credential abuse."],
            "explanation": "Approve immediate containment now.",
            "agent_comparison": {"graph": "Graph agent sees a broad attack path."},
            "suggestions": ["Deny and block now."],
        }

    server = MCPServer(vllm_callable=fake_vllm)
    result = server.analyze(
        event={"event_id": "evt-filter", "scenario": "credential_abuse"},
        agent_messages=[{"sender": "graph", "risk_signal": 0.9}],
        trust_scores={"graph": 0.8},
        conflict_score=0.2,
        deep_analysis_reasons=["high_novelty"],
    )
    assert result.structured_output["explanation"] == "filtered_by_mcp_output_filter"
    assert result.structured_output["suggestions"] == ["filtered_by_mcp_output_filter"]


def test_mcp_server_degrades_when_timeout_is_exceeded() -> None:
    def slow_vllm(_model: str, _context: dict[str, object], _timeout_ms: int) -> dict[str, object]:
        time.sleep(0.02)
        return {
            "hypotheses": ["Slow path hypothesis."],
            "explanation": "Slow response.",
            "agent_comparison": {},
            "suggestions": ["Re-check telemetry."],
        }

    server = MCPServer(vllm_callable=slow_vllm, timeout_ms=5)
    result = server.analyze(
        event={"event_id": "evt-timeout", "scenario": "slow_case"},
        agent_messages=[{"sender": "graph", "risk_signal": 0.4}],
        trust_scores={"graph": 0.7},
        conflict_score=0.4,
        deep_analysis_reasons=["agent_conflict"],
    )
    assert result.degraded_mode is True
    assert result.structured_output["explanation"] == "mcp_timeout_degraded"
    assert result.audit_log["timeout_exceeded"] is True


def test_mcp_server_uses_critical_review_profile_for_crown_jewel_case() -> None:
    captured: dict[str, object] = {}

    def fake_vllm(model: str, _context: dict[str, object], _timeout_ms: int) -> dict[str, object]:
        captured["model"] = model
        return {
            "hypotheses": ["Critical asset may require deeper review."],
            "explanation": "Structured advisory output.",
            "agent_comparison": {"graph": "Graph signal elevated."},
            "suggestions": ["Keep review bounded and advisory."],
        }

    server = MCPServer(vllm_callable=fake_vllm)
    result = server.analyze(
        event={"event_id": "evt-critical", "scenario": "tier0", "asset_criticality": 0.97, "blast_radius": 0.9},
        agent_messages=[{"sender": "graph", "risk_signal": 0.85}],
        trust_scores={"graph": 0.82},
        conflict_score=0.2,
        deep_analysis_reasons=["critical_asset"],
    )

    assert captured["model"] == "llama3-8b"
    assert result.audit_log["llm_profile"]["name"] == "critical_case_review"
    assert result.structured_output["advisory_only"] is True
