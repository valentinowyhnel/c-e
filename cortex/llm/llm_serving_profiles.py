from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMServingProfile:
    name: str
    runtime_model_id: str
    timeout_ms: int
    max_output_tokens: int
    temperature: float
    reasoning_depth: str
    use_case: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "runtime_model_id": self.runtime_model_id,
            "timeout_ms": self.timeout_ms,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "reasoning_depth": self.reasoning_depth,
            "use_case": self.use_case,
        }


FAST_REASONING = LLMServingProfile(
    name="fast_reasoning",
    runtime_model_id="mistral-7b",
    timeout_ms=120,
    max_output_tokens=320,
    temperature=0.0,
    reasoning_depth="fast",
    use_case="compare_agent_outputs, explain_risk, reasoning_summary",
)

DEEP_REASONING = LLMServingProfile(
    name="deep_reasoning",
    runtime_model_id="llama3-8b",
    timeout_ms=160,
    max_output_tokens=500,
    temperature=0.1,
    reasoning_depth="deep",
    use_case="generate_hypothesis, simulate_outcome, deep conflict review",
)

CRITICAL_CASE_REVIEW = LLMServingProfile(
    name="critical_case_review",
    runtime_model_id="llama3-8b",
    timeout_ms=190,
    max_output_tokens=560,
    temperature=0.1,
    reasoning_depth="critical",
    use_case="critical asset review, crown jewel cases, zero-day analysis",
)

SERVING_PROFILES = {
    FAST_REASONING.name: FAST_REASONING,
    DEEP_REASONING.name: DEEP_REASONING,
    CRITICAL_CASE_REVIEW.name: CRITICAL_CASE_REVIEW,
}
