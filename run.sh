#!/bin/zsh
# Start Studio for Qwen Image on http://127.0.0.1:8765 (loopback only) and open it in the browser.
set -euo pipefail
cd "$(dirname "$0")"
[[ -x .venv/bin/python ]] || { echo 'Run ./setup.sh first.'; exit 1; }
export QWEN_STUDIO_DATA="${QWEN_STUDIO_DATA:-$PWD/data}"
export HF_HOME="${HF_HOME:-$QWEN_STUDIO_DATA/hf-home}" HF_HUB_DISABLE_TELEMETRY=1 HF_XET_CHUNK_CACHE_SIZE_BYTES=0
export PYTORCH_ENABLE_MPS_FALLBACK=1 SDNQ_USE_TORCH_COMPILE=0 TOKENIZERS_PARALLELISM=false
# Cap MPS allocations at the GPU working set (~25 GB on a 32 GB Mac): an oversized job fails
# with a clear out-of-memory message instead of pushing the whole system into swap.
export PYTORCH_MPS_HIGH_WATERMARK_RATIO="${PYTORCH_MPS_HIGH_WATERMARK_RATIO:-1.0}" PYTORCH_MPS_LOW_WATERMARK_RATIO="${PYTORCH_MPS_LOW_WATERMARK_RATIO:-0.8}"
export QWEN_STUDIO_ATTN_BUDGET_MB="${QWEN_STUDIO_ATTN_BUDGET_MB:-512}" QWEN_STUDIO_KV_BUDGET_GB="${QWEN_STUDIO_KV_BUDGET_GB:-6}"
export QWEN_STUDIO_DTYPE="${QWEN_STUDIO_DTYPE:-auto}"
port="${QWEN_STUDIO_PORT:-8765}"
url="http://127.0.0.1:$port/"
if curl -s -o /dev/null "$url"; then echo "Already running: $url"; [[ -n "${QWEN_STUDIO_NO_BROWSER:-}" ]] || open "$url"; exit 0; fi
[[ -n "${QWEN_STUDIO_NO_BROWSER:-}" ]] || (sleep 2; open "$url") &
exec .venv/bin/python -X utf8 macos/backend/server.py --port "$port"
