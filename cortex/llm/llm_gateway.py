from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .llm_compression_pipeline import LLMCompressionPipeline
from .llm_model_registry import LLMModelRegistry
from .llm_serving_profiles import (
    CRITICAL_CASE_REVIEW,
    DEEP_REASONING,
    FAST_REASONING,
    LLMServingProfile,
)


class VLLMCallable(Protocol):
    def __call__(self, route_model: str, context: dict[str, object], timeout_ms: int) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class LLMGatewayResponse:
    raw_output: dict[str, object]
    profile: LLMServingProfile
    model_metadata: dict[str, object]


class LLMGateway:
    def __init__(
        self,
        *,
        vllm_callable: VLLMCallable,
        model_registry: LLMModelRegistry | None = None,
        compression_pipeline: LLMCompressionPipeline | None = None,
    ) -> None:
        self.vllm_callable = vllm_callable
        self.model_registry = model_registry or LLMModelRegistry()
        self.compression_pipeline = compression_pipeline or LLMCompressionPipeline()

    def select_profile(
        self,
        *,
        route_reason: str,
        route_model: str,
        context: dict[str, object],
    ) -> LLMServingProfile:
        payload = dict(context.get("payload", {}))
        event = dict(payload.get("event", {}))
        criticality = max(float(event.get("asset_criticality", 0.0)), float(event.get("blast_radius", 0.0)))
        if criticality >= 0.85:
            return CRITICAL_CASE_REVIEW
        if route_reason in {"inter_agent_conflict", "high_novelty_or_high_criticality"}:
            return DEEP_REASONING
        if route_model.startswith("llama"):
            return DEEP_REASONING
        return FAST_REASONING

    def invoke(
        self,
        *,
        route_reason: str,
        route_model: str,
        context: dict[str, object],
        timeout_ms: int,
    ) -> LLMGatewayResponse:
        profile = self.select_profile(
            route_reason=route_reason,
            route_model=route_model,
            context=context,
        )
        effective_model = profile.runtime_model_id
        raw_output = self.vllm_callable(effective_model, context, min(timeout_ms, profile.timeout_ms))
        registered_model = self.model_registry.get(effective_model)
        compression_recipe = self.compression_pipeline.recipe_for_profile(profile.name)
        metadata = {
            "profile": profile.to_dict(),
            "registered_model": registered_model.to_dict() if registered_model else None,
            "compression_recipe": compression_recipe.to_dict(),
            "route_model_requested": route_model,
        }
        return LLMGatewayResponse(
            raw_output=raw_output,
            profile=profile,
            model_metadata=metadata,
        )
