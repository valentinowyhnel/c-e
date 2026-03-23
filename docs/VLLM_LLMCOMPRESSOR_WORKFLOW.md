# vLLM Compression Workflow With LLM Compressor

This repository can compress Hugging Face checkpoints into `safetensors` artifacts that remain compatible with `vLLM`.

The workflow is intentionally separate from the `cortex-vllm` HTTP runtime:

- runtime serving stays minimal
- compression dependencies stay optional
- dry-run remains available before writing model artifacts

## Install

From [`services/cortex-vllm`](C:/Users/dell/Desktop/coco/services/cortex-vllm):

```bash
pip install .[compression]
```

Pinned dependency:

- `llmcompressor==0.10.0.1`

Source references:

- `llmcompressor` README: https://github.com/vllm-project/llm-compressor
- `oneshot` API docs: https://docs.vllm.ai/projects/llm-compressor/en/stable/reference/llmcompressor/entrypoints/oneshot/

## Dry Run

Dry-run first, per Cortex contract:

```bash
python scripts/runtime/compress-vllm-model.py \
  --model-id microsoft/Phi-3-mini-4k-instruct \
  --scheme W4A16 \
  --ignore lm_head \
  --dry-run
```

The dry-run prints:

- the compression plan
- the quantization recipe
- the manifest that would be written with the compressed checkpoint

## Execute Compression

Example:

```bash
python scripts/runtime/compress-vllm-model.py \
  --model-id meta-llama/Meta-Llama-3-8B-Instruct \
  --scheme FP8_BLOCK \
  --ignore lm_head \
  --ignore "re:.*mlp.gate$" \
  --dataset HuggingFaceH4/ultrachat_200k \
  --split "train_sft[:256]" \
  --text-column messages \
  --num-calibration-samples 256 \
  --max-seq-length 4096
```

Artifacts are written by default under:

```text
artifacts/models/<model-slug>-<scheme-lower>
```

Each output directory includes:

- compressed `safetensors` checkpoint files
- tokenizer files
- `compression-manifest.json`

## Notes

- The compression path uses `llmcompressor.oneshot` and `QuantizationModifier`.
- The implementation loads the checkpoint through `transformers` with `device_map="auto"` so large-model loading can use the library stack expected by `llmcompressor`.
- `trust_remote_code` remains opt-in.
- This workflow does not change live model routing by itself. Deployment into `cortex-vllm` remains a separate operator action.
