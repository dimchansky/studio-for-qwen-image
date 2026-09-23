#!/bin/zsh
# Build the local runtime (.venv) for Qwen Image Studio on Apple Silicon.
set -euo pipefail
cd "$(dirname "$0")"
[[ "$(uname -m)" == arm64 ]] || { echo 'Requires an Apple Silicon Mac.'; exit 1; }
python="${QWEN_STUDIO_BOOTSTRAP_PYTHON:-/opt/homebrew/bin/python3.12}"
"$python" -c 'import sys, platform; assert sys.version_info[:2] == (3, 12) and platform.machine() == "arm64", "Use arm64 Python 3.12"'
[[ -x .venv/bin/python ]] || "$python" -m venv .venv
export PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r macos/requirements.txt
.venv/bin/python - <<'PY'
import torch, diffusers, mlx.core as mx
from diffusers import QwenImage21Pipeline
print('torch', torch.__version__, 'MPS available:', torch.backends.mps.is_available())
print('diffusers', diffusers.__version__, '| mlx', mx.__version__)
PY
echo 'Setup complete. Start the studio with ./run.sh'
