#!/bin/bash
set -euo pipefail

echo "Prepare a writable volume or PVC mounted at /models before downloading GGUF models."
echo "Expected files:"
echo "  - phi-3-mini-4k-instruct-q4_k_m.gguf"
echo "  - mistral-7b-instruct-v0.3-q4_k_m.gguf"
echo "GPU-backed Hugging Face models are pulled at runtime by vLLM."
