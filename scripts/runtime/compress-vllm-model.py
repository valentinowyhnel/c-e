from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "services" / "cortex-vllm"))

from cortex_vllm.compression import (
    CompressionPlan,
    SUPPORTED_SCHEMES,
    default_output_dir,
    dry_run_report,
    run_oneshot_compression,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compress a Hugging Face model into a llmcompressor safetensors checkpoint compatible with vLLM."
    )
    parser.add_argument("--model-id", required=True, help="Hugging Face model id or local checkpoint path.")
    parser.add_argument(
        "--scheme",
        default="W4A16",
        choices=sorted(SUPPORTED_SCHEMES),
        help="Quantization scheme to apply.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Target directory for the compressed checkpoint. Defaults to artifacts/models/<model>-<scheme>.",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Module names or regex selectors to exclude from quantization. May be repeated.",
    )
    parser.add_argument(
        "--dataset",
        default="HuggingFaceH4/ultrachat_200k",
        help="Calibration dataset identifier.",
    )
    parser.add_argument("--split", default="train_sft[:128]", help="Calibration split expression.")
    parser.add_argument("--text-column", default="messages", help="Dataset column passed to llmcompressor.")
    parser.add_argument("--num-calibration-samples", type=int, default=128, help="Calibration sample count.")
    parser.add_argument("--max-seq-length", type=int, default=2048, help="Maximum calibration sequence length.")
    parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="Allow transformers remote code execution when loading the checkpoint.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the compression plan and exit without writing the checkpoint.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir or default_output_dir(args.model_id, args.scheme)
    plan = CompressionPlan(
        model_id=args.model_id,
        output_dir=str(Path(output_dir)),
        scheme=args.scheme,
        ignore=tuple(args.ignore),
        dataset=args.dataset,
        split=args.split,
        text_column=args.text_column,
        num_calibration_samples=args.num_calibration_samples,
        max_seq_length=args.max_seq_length,
        trust_remote_code=args.trust_remote_code,
    )

    if args.dry_run:
        print(dry_run_report(plan))
        return 0

    manifest_path = run_oneshot_compression(plan)
    print(f"Compression complete. Manifest written to {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
