from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegisteredLLMModel:
    runtime_model_id: str
    source_model_id: str
    compression_scheme: str | None
    quality_score: float
    memory_cost_gb: float
    latency_budget_ms: int
    profile_names: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "runtime_model_id": self.runtime_model_id,
            "source_model_id": self.source_model_id,
            "compression_scheme": self.compression_scheme,
            "quality_score": self.quality_score,
            "memory_cost_gb": self.memory_cost_gb,
            "latency_budget_ms": self.latency_budget_ms,
            "profile_names": list(self.profile_names),
        }


class LLMModelRegistry:
    def __init__(self) -> None:
        self._models: dict[str, RegisteredLLMModel] = {
            "mistral-7b": RegisteredLLMModel(
                runtime_model_id="mistral-7b",
                source_model_id="mistralai/Mistral-7B-Instruct-v0.3",
                compression_scheme="W4A16",
                quality_score=0.87,
                memory_cost_gb=4.0,
                latency_budget_ms=120,
                profile_names=("fast_reasoning",),
            ),
            "llama3-8b": RegisteredLLMModel(
                runtime_model_id="llama3-8b",
                source_model_id="meta-llama/Meta-Llama-3-8B-Instruct",
                compression_scheme="W8A8",
                quality_score=0.93,
                memory_cost_gb=8.5,
                latency_budget_ms=190,
                profile_names=("deep_reasoning", "critical_case_review"),
            ),
            "phi3-mini": RegisteredLLMModel(
                runtime_model_id="phi3-mini",
                source_model_id="microsoft/Phi-3-mini-4k-instruct",
                compression_scheme="W4A16",
                quality_score=0.8,
                memory_cost_gb=2.4,
                latency_budget_ms=90,
                profile_names=("fast_reasoning",),
            ),
        }

    def get(self, runtime_model_id: str) -> RegisteredLLMModel | None:
        return self._models.get(runtime_model_id)
