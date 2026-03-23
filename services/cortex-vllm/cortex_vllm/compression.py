from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


SUPPORTED_SCHEMES = {"W4A16", "FP8_BLOCK", "W8A8"}


@dataclass(frozen=True)
class CompressionPlan:
    model_id: str
    output_dir: str
    scheme: str
    ignore: tuple[str, ...]
    dataset: str
    split: str
    text_column: str
    num_calibration_samples: int
    max_seq_length: int
    trust_remote_code: bool = False

    def validate(self) -> None:
        if self.scheme not in SUPPORTED_SCHEMES:
            raise ValueError(f"unsupported scheme: {self.scheme}")
        if self.num_calibration_samples <= 0:
            raise ValueError("num_calibration_samples must be > 0")
        if self.max_seq_length <= 0:
            raise ValueError("max_seq_length must be > 0")
        if not self.model_id.strip():
            raise ValueError("model_id is required")
        if not self.output_dir.strip():
            raise ValueError("output_dir is required")


def default_output_dir(model_id: str, scheme: str) -> str:
    model_slug = model_id.rstrip("/").split("/")[-1]
    return str(Path("artifacts") / "models" / f"{model_slug}-{scheme.lower()}")


def build_quantization_recipe(plan: CompressionPlan) -> dict[str, object]:
    plan.validate()
    return {
        "targets": "Linear",
        "scheme": plan.scheme,
        "ignore": list(plan.ignore),
    }


def build_manifest(plan: CompressionPlan) -> dict[str, object]:
    plan.validate()
    return {
        "model_id": plan.model_id,
        "output_dir": plan.output_dir,
        "scheme": plan.scheme,
        "ignore": list(plan.ignore),
        "calibration": {
            "dataset": plan.dataset,
            "split": plan.split,
            "text_column": plan.text_column,
            "num_calibration_samples": plan.num_calibration_samples,
            "max_seq_length": plan.max_seq_length,
        },
        "artifacts": {
            "format": "safetensors",
            "vllm_compatible": True,
        },
        "execution": {
            "dry_run_supported": True,
            "accelerate_path_expected": True,
            "trust_remote_code": plan.trust_remote_code,
        },
        "generated_at": datetime.now(UTC).isoformat(),
    }


def write_manifest(plan: CompressionPlan) -> Path:
    manifest = build_manifest(plan)
    output_path = Path(plan.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    manifest_path = output_path / "compression-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def dry_run_report(plan: CompressionPlan) -> str:
    manifest = build_manifest(plan)
    payload = {
        "plan": asdict(plan),
        "recipe": build_quantization_recipe(plan),
        "manifest": manifest,
    }
    return json.dumps(payload, indent=2)


def run_oneshot_compression(plan: CompressionPlan) -> Path:
    plan.validate()

    try:
        from llmcompressor import oneshot
        from llmcompressor.modifiers.quantization import QuantizationModifier
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "llmcompressor dependencies missing. Install with `pip install .[compression]` from services/cortex-vllm."
        ) from exc

    recipe_config = build_quantization_recipe(plan)
    recipe = QuantizationModifier(
        targets=recipe_config["targets"],
        scheme=recipe_config["scheme"],
        ignore=recipe_config["ignore"],
    )

    model = AutoModelForCausalLM.from_pretrained(
        plan.model_id,
        torch_dtype="auto",
        device_map="auto",
        trust_remote_code=plan.trust_remote_code,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        plan.model_id,
        trust_remote_code=plan.trust_remote_code,
    )

    oneshot(
        model=model,
        recipe=recipe,
        output_dir=plan.output_dir,
        dataset=plan.dataset,
        split=plan.split,
        text_column=plan.text_column,
        num_calibration_samples=plan.num_calibration_samples,
        max_seq_length=plan.max_seq_length,
    )

    model.save_pretrained(plan.output_dir, safe_serialization=True)
    tokenizer.save_pretrained(plan.output_dir)
    return write_manifest(plan)
