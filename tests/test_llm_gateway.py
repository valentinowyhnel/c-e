from __future__ import annotations

from cortex.llm import LLMGateway


def test_llm_gateway_uses_fast_profile_for_fast_path() -> None:
    seen: dict[str, object] = {}

    def fake_vllm(model: str, _context: dict[str, object], timeout_ms: int) -> dict[str, object]:
        seen["model"] = model
        seen["timeout_ms"] = timeout_ms
        return {"hypotheses": [], "explanation": "ok", "agent_comparison": {}, "suggestions": []}

    gateway = LLMGateway(vllm_callable=fake_vllm)
    response = gateway.invoke(
        route_reason="fast_advisory_path",
        route_model="phi-3-mini-4k-instruct",
        context={"payload": {"event": {"asset_criticality": 0.2}}},
        timeout_ms=100,
    )

    assert seen["model"] == "mistral-7b"
    assert response.profile.name == "fast_reasoning"
    assert response.model_metadata["compression_recipe"]["scheme"] == "W4A16"


def test_llm_gateway_uses_critical_profile_for_critical_case() -> None:
    seen: dict[str, object] = {}

    def fake_vllm(model: str, _context: dict[str, object], timeout_ms: int) -> dict[str, object]:
        seen["model"] = model
        seen["timeout_ms"] = timeout_ms
        return {"hypotheses": [], "explanation": "ok", "agent_comparison": {}, "suggestions": []}

    gateway = LLMGateway(vllm_callable=fake_vllm)
    response = gateway.invoke(
        route_reason="high_novelty_or_high_criticality",
        route_model="llama3-8b-instruct",
        context={"payload": {"event": {"asset_criticality": 0.95}}},
        timeout_ms=220,
    )

    assert seen["model"] == "llama3-8b"
    assert seen["timeout_ms"] == 190
    assert response.profile.name == "critical_case_review"
