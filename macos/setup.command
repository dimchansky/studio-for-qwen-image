#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"
trap 'echo "Setup did not finish. Read the error above, then run setup.command again."' ZERR
if [[ "$(uname -m)" != arm64 ]]; then
  echo 'This package requires an Apple Silicon Mac.'; exit 1
fi
studio_python="${QWEN_STUDIO_PYTHON_BOOTSTRAP:-}"
if [[ -z "$studio_python" ]]; then
  for candidate in /Library/Frameworks/Python.framework/Versions/{3.11,3.10,3.12,3.13}/bin/python3 /opt/homebrew/bin/python3; do
    if [[ -x "$candidate" ]]; then studio_python="$candidate"; break; fi
  done
fi
if [[ -z "$studio_python" ]]; then
  echo 'Install Python 3.11 from https://www.python.org/downloads/macos/ and run setup.command again.'
  exit 1
fi
"$studio_python" -c 'import sys,platform; assert (3,10) <= sys.version_info[:2] < (3,14) and platform.machine()=="arm64", "Use arm64 Python 3.10-3.13"'
studio_data="${QWEN_STUDIO_DATA:-$HOME/Library/Application Support/Qwen Studio}"
studio_runtime="$studio_data/runtime"
mkdir -p "$studio_data"
if [[ ! -x "$studio_runtime/bin/python3" ]]; then "$studio_python" -m venv "$studio_runtime"; fi
"$studio_runtime/bin/python3" -m pip install --upgrade pip
"$studio_runtime/bin/python3" -m pip install -r requirements.txt
"$studio_runtime/bin/python3" -c 'import torch; from diffusers import QwenImage21Pipeline; print("PyTorch:",torch.__version__); print("MPS available:",torch.backends.mps.is_available())'
echo 'Setup complete. Open Qwen Studio.app, then choose a model source in the app.'
