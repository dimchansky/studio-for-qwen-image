#!/bin/zsh
# Download pinned model files into data/models (resumable, SHA-256 verified).
#   ./download.sh                 core files: everything needed for all modes (~20 GB)
#   ./download.sh --all           core + optional files (uncensored model, prompt enhancers, ~39 GB)
#   ./download.sh pe_t2i pe_i2i   specific components (see macos/backend/models.json)
# The same downloads are available in the web UI under Settings → Model files.
set -euo pipefail
cd "$(dirname "$0")"
[[ -x .venv/bin/python ]] || { print -u2 'Run ./setup.sh first.'; exit 1; }
export QWEN_STUDIO_DATA="${QWEN_STUDIO_DATA:-$PWD/data}"
export HF_HOME="${HF_HOME:-$QWEN_STUDIO_DATA/hf-home}" HF_HUB_DISABLE_TELEMETRY=1 HF_XET_CHUNK_CACHE_SIZE_BYTES=0
core=(base text_encoder transformer_official turbo)
optional=(transformer_uc pe_t2i pe_i2i)
if (( $# == 0 )); then components=($core)
elif [[ "$1" == --all ]]; then components=($core $optional)
else components=("$@"); fi
exec .venv/bin/python -u macos/backend/download.py "$QWEN_STUDIO_DATA/models" $components
