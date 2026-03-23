from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompressionRecipe:
    profile_name: str
    scheme: str
    dataset_name: str
    text_column: str
    num_calibration_samples: int
    max_seq_length: int

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_name": self.profile_name,
            "scheme": self.scheme,
            "dataset_name": self.dataset_name,
            "text_column": self.text_column,
            "num_calibration_samples": self.num_calibration_samples,
            "max_seq_length": self.max_seq_length,
        }


class LLMCompressionPipeline:
    def recipe_for_profile(self, profile_name: str) -> CompressionRecipe:
        if profile_name == "critical_case_review":
            return CompressionRecipe(
                profile_name=profile_name,
                scheme="W8A8",
                dataset_name="cortex-critical-calibration",
                text_column="text",
                num_calibration_samples=512,
                max_seq_length=4096,
            )
        if profile_name == "deep_reasoning":
            return CompressionRecipe(
                profile_name=profile_name,
                scheme="W8A8",
                dataset_name="cortex-deep-reasoning-calibration",
                text_column="text",
                num_calibration_samples=384,
                max_seq_length=3072,
            )
        return CompressionRecipe(
            profile_name="fast_reasoning",
            scheme="W4A16",
            dataset_name="cortex-fast-reasoning-calibration",
            text_column="text",
            num_calibration_samples=256,
            max_seq_length=2048,
        )
