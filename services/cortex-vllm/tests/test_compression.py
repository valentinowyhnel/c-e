from __future__ import annotations

import json

from cortex_vllm.compression import (
    CompressionPlan,
    build_manifest,
    build_quantization_recipe,
    default_output_dir,
    dry_run_report,
)


def test_default_output_dir_includes_model_slug_and_scheme() -> None:
    assert default_output_dir("microsoft/Phi-3-mini-4k-instruct", "W4A16").endswith(
        "Phi-3-mini-4k-instruct-w4a16"
    )


def test_build_quantization_recipe_uses_linear_targets() -> None:
    plan = CompressionPlan(
        model_id="microsoft/Phi-3-mini-4k-instruct",
        output_dir="artifacts/models/phi3-mini-w4a16",
        scheme="W4A16",
        ignore=("lm_head",),
        dataset="HuggingFaceH4/ultrachat_200k",
        split="train_sft[:128]",
        text_column="messages",
        num_calibration_samples=128,
        max_seq_length=2048,
    )

    recipe = build_quantization_recipe(plan)

    assert recipe["targets"] == "Linear"
    assert recipe["scheme"] == "W4A16"
    assert recipe["ignore"] == ["lm_head"]


def test_dry_run_report_contains_vllm_compatible_manifest() -> None:
    plan = CompressionPlan(
        model_id="meta-llama/Meta-Llama-3-8B-Instruct",
        output_dir="artifacts/models/llama3-8b-fp8",
        scheme="FP8_BLOCK",
        ignore=("lm_head", "re:.*mlp.gate$"),
        dataset="HuggingFaceH4/ultrachat_200k",
        split="train_sft[:256]",
        text_column="messages",
        num_calibration_samples=256,
        max_seq_length=4096,
    )

    report = json.loads(dry_run_report(plan))
    manifest = report["manifest"]

    assert manifest["artifacts"]["format"] == "safetensors"
    assert manifest["artifacts"]["vllm_compatible"] is True
    assert manifest["execution"]["dry_run_supported"] is True


def test_manifest_contains_calibration_details() -> None:
    plan = CompressionPlan(
        model_id="mistralai/Mistral-7B-Instruct-v0.3",
        output_dir="artifacts/models/mistral-7b-w8a8",
        scheme="W8A8",
        ignore=(),
        dataset="HuggingFaceH4/ultrachat_200k",
        split="train_sft[:64]",
        text_column="messages",
        num_calibration_samples=64,
        max_seq_length=1024,
    )

    manifest = build_manifest(plan)

    assert manifest["calibration"]["dataset"] == "HuggingFaceH4/ultrachat_200k"
    assert manifest["calibration"]["num_calibration_samples"] == 64
